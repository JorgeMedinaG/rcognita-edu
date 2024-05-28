#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Preset: a 3-wheel robot (kinematic model a. k. a. non-holonomic integrator).

"""

import os, sys
PARENT_DIR = os.path.abspath(__file__ + '/../..')
sys.path.insert(0, PARENT_DIR)
import math

import pathlib
    
import warnings
import csv
from datetime import datetime, timedelta
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np


import simulator
import systems
import controllers
import loggers
import visuals
from utilities import on_key_press

import argparse

#---------------------------------------- Import ROS
import rospy
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Point, Twist
#from tf.transformations import euler_from_quaternion
import tf.transformations as tftr 
import threading


class ROS_preset:

    def __init__(self, ctrl_mode, state_goal, state_init, my_ctrl_nominal, my_sys, my_ctrl_benchmarking, my_logger=None, datafile=None):
        
        self.RATE = rospy.get_param('/rate', 50)
        self.lock = threading.Lock()
        
        #Initialization
        self.state_init = state_init
        self.state_goal = state_goal
        self.system = my_sys
        
        self.ctrl_nominal = my_ctrl_nominal
        self.ctrl_benchm = my_ctrl_benchmarking
        
        self.dt = 0.0
        self.time_start = 0.0
        
        # Topics
        
        self.pub_cmd_vel = rospy.Publisher("/cmd_vel", Twist, queue_size=1, latch=False)
        self.sub_odom = rospy.Subscriber("/odom", Odometry, self.odometry_callback)
        
        self.state = np.zeros(3)
        self.dstate = np.zeros(3)
        self.new_state = np.zeros(3)
        self.new_dstate = np.zeros(3)
        
        self.datafiles = datafile
        self.logger = my_logger
        self.ctrl_mode = ctrl_mode
        
        self.rotation_counter = 0
        self.prev_theta = 0
        self.new_theta = 0
        
        theta_goal = self.state_goal[2]
        
        # Complete Rotation Matrix
        self.rotation_matrix = np.zeros((3,3))  # here
        
    def odometry_callback(self, msg):
    
        self.lock.acquire()
        
        # Read current robot state
        x = msg.pose.pose.position.x
        # Complete for y and orientation
        y = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
          
        # Transform quat2euler using tf transformations: complete!
        current_rpy = tftr.euler_from_quaternion([q.x, q.y, q.z, q.w])
        
        # Extract Theta (orientation about Z)
        theta = current_rpy[2]
        
        self.state = [x, y, 0, theta]
        
        # Make transform matrix from 'robot body' frame to 'goal' frame
        theta_goal = self.state_goal[2]
        
        # Complete rotation matrix
        rotation_matrix = np.array([ [np.cos(theta), -np.sin(theta), 0], 
                                    [np.sin(theta), np.cos(theta), 0], 
                                    [0,0,1] 
                                    ])
        
        state_matrix = np.vstack([
            [self.state_goal[0]],
            [self.state_goal[1]],
            [0]
        ]) # [x, y, 0] -- column   
        
        # Compute Transformation matrix 
        
        t_matrix = np.block([rotation_matrix, state_matrix], 
                            [np.array([0,0,0,1])]
                            ) # Complete
        inv_t_matrix = np.linalg.inv(t_matrix)
        
        # Complete rotation counter for turtlebot3
        
        ''' Your solution goes here (rotation_counter) '''
        if math.copysign(1, self.prev_theta) != math.copysign(1, theta) and abs(self.prev_theta) > np.pi:
            if math.copysign(1, self.prev_theta) == -1:
                self.rotation_counter -= 1
            else: 
                self.rotation_counter += 1
        
        self.prev_theta = theta
        theta = theta + 2 * np.pi * self.rotation_counter
        self.new_theta = theta
        
        # Orientation transform
        new_theta = theta - theta_goal
        
        # Do position transform
        
        ''' 
        Your solution goes here 
        self.new_state = using tranformations :) Have fun!
        '''
        temp_pos = np.array([x,y,0,1])
        self.new_state = np.linalg.inv(self.t_matrix) @ temp_pos.T
        self.new_state = [self.new_state[0], self.new_state[1], new_theta]
        
        self.lock.release()
        
    def spin(self, is_print_sim_step=False, is_log_data=False):
    
        rospy.loginfo('ROS-Preset has been activated!')
        start_time = datetime.now()
        rate = rospy.Rate(self.RATE)
        self.time_start = rospy.get_time()
        
        while not rospy.is_shutdown() and datetime.now() - start_time < timedelta(100):
            if not all(self.new_state):
                rate.sleep()

            t = rospy.get_time() - self.time_start
            self.t = t
            
            velocity = Twist()
            
            # action = controllers.ctrl_selector('''COMPLETE!''')
            action = controllers.ctrl_selector(t, 
                                    self.new_state, 
                                    None, 
                                    self.ctrl_nominal, 
                                    self.ctrl_benchm, 
                                    self.ctrl_mode)
            
            self.system.receive_action(action)
            # self.ctrl_benchm.receive_sys.state(self.system._state)
            self.ctrl_benchm.upd_accum_obj(self.new_state, action)
            
            run_obj = self.ctrl_benchm.run_obj(self.new_state, action)
            accum_obj = self.ctrl_benchm.accum_obj_val
            
            if is_print_sim_step:
                self.logger.print_sim_step(t, self.new_state[0], self.new_state[1], self.new_state[2], run_obj, accum_obj, action)
                
            if is_print_sim_step:
                self.logger.log_data_row(self.datafiles[0], t, self.new_state[0], self.new_state[1], self.new_state[2], run_obj, accum_obj, action)
                
            self.ctrl_benchm.receive_sys_state(self.new_state)
           
           # Generate ROSmsg from action
            '''
            velocity.linear.x =  ...
            velocity.angular.z =  ...
            
            PUBLISH THE MESSAGE VELOCITY:
            YOUR SOLUTION HERE
            '''
            velocity.linear.x = action[0]
            velocity.angular.z = action[1]
            self.pub_cmd_vel.publish(velocity)
           
            rate.sleep()
           
        rospy.loginfo('Task completed or interrupted!')
       
if __name__ == "__main__":
	rospy.init_node('ros_preset_node')
#----------------------------------------Set up dimensions
dim_state = 3
dim_input = 2
dim_output = dim_state
dim_disturb = 2

dim_R1 = dim_output + dim_input
dim_R2 = dim_R1

description = "Agent-environment preset: a 3-wheel robot (kinematic model a. k. a. non-holonomic integrator)."

parser = argparse.ArgumentParser(description=description)

parser.add_argument('--ctrl_mode', metavar='ctrl_mode', type=str,
                choices=['manual',
                         'nominal',
                         'MPC',
                         'RQL',
                         'SQL',
                         'JACS'],
                default='nominal',
                help='Control mode. Currently available: ' +
                '----manual: manual constant control specified by action_manual; ' +
                '----nominal: nominal controller, usually used to benchmark optimal controllers;' +                     
                '----MPC:model-predictive control; ' +
                '----RQL: Q-learning actor-critic with Nactor-1 roll-outs of stage objective; ' +
                '----SQL: stacked Q-learning; ' + 
                '----JACS: joint actor-critic (stabilizing), system-specific, needs proper setup.')
parser.add_argument('--dt', type=float, metavar='dt',
                default=0.01,
                help='Controller sampling time.' )
parser.add_argument('--t1', type=float, metavar='t1',
                default=10.0,
                help='Final time of episode.' )
parser.add_argument('--Nruns', type=int,
                default=1,
                help='Number of episodes. Learned parameters are not reset after an episode.')
parser.add_argument('--state_init', type=str, nargs="+", metavar='state_init',
                default=['5', '5', '-3*pi/4'],
                help='Initial state (as sequence of numbers); ' + 
                'dimension is environment-specific!')
parser.add_argument('--goal_pose_x', type=float,
                    default=3.0,
                    help='x-coordinate of the robot pose.')
parser.add_argument('--goal_pose_y', type=float,
                    default=3.0,
                    help='y-coordinate of the robot pose.')
parser.add_argument('--goal_pose_theta', type=float,
                    default=0.001,
                    help='orientation angle (in radians) of the robot pose.')
parser.add_argument('--is_log_data', type=bool,
                default=False,
                help='Flag to log data into a data file. Data are stored in simdata folder.')
parser.add_argument('--is_visualization', type=bool,
                default=True,
                help='Flag to produce graphical output.')
parser.add_argument('--is_print_sim_step', type=bool,
                default=True,
                help='Flag to print simulation data into terminal.')
parser.add_argument('--is_est_model', type=bool,
                default=False,
                help='Flag to estimate environment model.')
parser.add_argument('--model_est_stage', type=float,
                default=1.0,
                help='Seconds to learn model until benchmarking controller kicks in.')
parser.add_argument('--model_est_period_multiplier', type=float,
                default=1,
                help='Model is updated every model_est_period_multiplier times dt seconds.')
parser.add_argument('--model_order', type=int,
                default=5,
                help='Order of state-space estimation model.')
parser.add_argument('--prob_noise_pow', type=float,
                default=False,
                help='Power of probing (exploration) noise.')
parser.add_argument('--action_manual', type=float,
                default=[-5, -3], nargs='+',
                help='Manual control action to be fed constant, system-specific!')
parser.add_argument('--Nactor', type=int,
                default=3,
                help='Horizon length (in steps) for predictive controllers.')
parser.add_argument('--pred_step_size_multiplier', type=float,
                default=1.0,
                help='Size of each prediction step in seconds is a pred_step_size_multiplier multiple of controller sampling time dt.')
parser.add_argument('--buffer_size', type=int,
                default=10,
                help='Size of the buffer (experience replay) for model estimation, agent learning etc.')
parser.add_argument('--stage_obj_struct', type=str,
                default='quadratic',
                choices=['quadratic',
                         'biquadratic'],
                help='Structure of stage objective function.')
parser.add_argument('--R1_diag', type=float, nargs='+',
                default=[1, 10, 1, 0, 0],
                help='Parameter of stage objective function. Must have proper dimension. ' +
                'Say, if chi = [observation, action], then a quadratic stage objective reads chi.T diag(R1) chi, where diag() is transformation of a vector to a diagonal matrix.')
parser.add_argument('--R2_diag', type=float, nargs='+',
                default=[1, 10, 1, 0, 0],
                help='Parameter of stage objective function . Must have proper dimension. ' + 
                'Say, if chi = [observation, action], then a bi-quadratic stage objective reads chi**2.T diag(R2) chi**2 + chi.T diag(R1) chi, ' +
                'where diag() is transformation of a vector to a diagonal matrix.')
parser.add_argument('--Ncritic', type=int,
                default=4,
                help='Critic stack size (number of temporal difference terms in critic cost).')
parser.add_argument('--gamma', type=float,
                default=1.0,
                help='Discount factor.')
parser.add_argument('--critic_period_multiplier', type=float,
                default=1.0,
                help='Critic is updated every critic_period_multiplier times dt seconds.')
parser.add_argument('--critic_struct', type=str,
                default='quad-nomix', choices=['quad-lin',
                                               'quadratic',
                                               'quad-nomix',
                                               'quad-mix'],
                help='Feature structure (critic). Currently available: ' +
                '----quad-lin: quadratic-linear; ' +
                '----quadratic: quadratic; ' +
                '----quad-nomix: quadratic, no mixed terms; ' +
                '----quad-mix: quadratic, mixed observation-action terms (for, say, Q or advantage function approximations).')
parser.add_argument('--actor_struct', type=str,
                default='quad-nomix', choices=['quad-lin',
                                               'quadratic',
                                               'quad-nomix'],
                help='Feature structure (actor). Currently available: ' +
                '----quad-lin: quadratic-linear; ' +
                '----quadratic: quadratic; ' +
                '----quad-nomix: quadratic, no mixed terms.')
parser.add_argument('--seed', type=int, default=1,help='Seed for random number generation.')
args = parser.parse_args()

#----------------------------------------Post-processing of arguments
# Convert `pi` to a number pi
for k in range(len(args.state_init)):
	args.state_init[k] = eval( args.state_init[k].replace('pi', str(np.pi)) )

args.state_init = np.array(args.state_init)
args.action_manual = np.array(args.action_manual)

pred_step_size = args.dt * args.pred_step_size_multiplier
model_est_period = args.dt * args.model_est_period_multiplier
critic_period = args.dt * args.critic_period_multiplier

R1 = np.diag(np.array(args.R1_diag))
R2 = np.diag(np.array(args.R2_diag))

assert args.t1 > args.dt > 0.0
assert args.state_init.size == dim_state

globals().update(vars(args))

#----------------------------------------(So far) fixed settings
is_disturb = 0
is_dyn_ctrl = 0

t0 = 0

action_init = 0 * np.ones(dim_input)

# Solver
atol = 1e-5
rtol = 1e-3

# xy-plane
xMin = -10
xMax = 10
yMin = -10
yMax = 10

# Model estimator stores models in a stack and recall the best of model_est_checks
model_est_checks = 0

# Control constraints
v_min = -25
v_max = 25
omega_min = -5
omega_max = 5
ctrl_bnds=np.array([[v_min, v_max], [omega_min, omega_max]])

#----------------------------------------Initialization : : system
my_sys = systems.Sys3WRobotNI(sys_type="diff_eqn",
                                 dim_state=dim_state,
                                 dim_input=dim_input,
                                 dim_output=dim_output,
                                 dim_disturb=dim_disturb,
                                 pars=[],
                                 ctrl_bnds=ctrl_bnds,
                                 is_dyn_ctrl=is_dyn_ctrl,
                                 is_disturb=is_disturb,
                                 pars_disturb = np.array([[200*dt, 200*dt], [0, 0], [0.3, 0.3]]))

observation_init = my_sys.out(state_init)

xCoord0 = state_init[0]
yCoord0 = state_init[1]
alpha0 = state_init[2]
alpha_deg_0 = alpha0/2/np.pi

#----------------------------------------Initialization : : model

#----------------------------------------Initialization : : controller
my_ctrl_nominal = controllers.N_CTRL(ctrl_bnds, [args.goal_pose_x, args.goal_pose_y,args.goal_pose_theta])

# Predictive optimal controller
my_ctrl_opt_pred = controllers.ControllerOptimalPredictive(dim_input,
                                    dim_output,
                                    args.ctrl_mode,
                                    ctrl_bnds = ctrl_bnds,
                                    action_init = [],
                                    t0 = t0,
                                    sampling_time = args.dt,
                                    Nactor = args.Nactor,
                                    pred_step_size = pred_step_size,
                                    sys_rhs = my_sys._state_dyn,
                                    sys_out = my_sys.out,
                                    state_sys = state_init,
                                    buffer_size = args.buffer_size,
                                    gamma = args.gamma,
                                    Ncritic = args.Ncritic,
                                    critic_period = critic_period,
                                    critic_struct = args.critic_struct,
                                    run_obj_struct = args.stage_obj_struct,
                                    run_obj_pars = [R1],
                                    observation_target = [0, 0, 0],
                                    state_init=state_init,
                                    obstacle=[],
                                    seed=seed)


my_ctrl_benchm = my_ctrl_opt_pred

#----------------------------------------Initialization : : simulator
my_simulator = simulator.Simulator(sys_type = "diff_eqn",
                               closed_loop_rhs = my_sys.closed_loop_rhs,
                               sys_out = my_sys.out,
                               state_init = state_init,
                               disturb_init = np.array([0, 0]),
                               action_init = action_init,
                               t0 = t0,
                               t1 = t1,
                               dt = dt,
                               max_step = dt/2,
                               first_step = 1e-6,
                               atol = atol,
                               rtol = rtol,
                               is_disturb = is_disturb,
                               is_dyn_ctrl = is_dyn_ctrl)

#----------------------------------------Initialization : : logger
if os.path.basename( os.path.normpath( os.path.abspath(os.getcwd()) ) ) == 'presets':
	data_folder = '../simdata'
else:
	data_folder = 'simdata'

pathlib.Path(data_folder).mkdir(parents=True, exist_ok=True) 

date = datetime.now().strftime("%Y-%m-%d")
time = datetime.now().strftime("%Hh%Mm%Ss")
datafiles = [None] * Nruns

for k in range(0, Nruns):
	datafiles[k] = data_folder + '/' + my_sys.name + '__' + ctrl_mode + '__' + date + '__' + time + '__run{run:02d}.csv'.format(run=k+1)

if is_log_data:
    print('Logging data to:    ' + datafiles[k])
        
    with open(datafiles[k], 'w', newline='') as outfile:
        writer = csv.writer(outfile)
        writer.writerow(['System', my_sys.name ] )
        writer.writerow(['Controller', ctrl_mode ] )
        writer.writerow(['dt', str(dt) ] )
        writer.writerow(['state_init', str(state_init) ] )
        writer.writerow(['is_est_model', str(is_est_model) ] )
        writer.writerow(['model_est_stage', str(model_est_stage) ] )
        writer.writerow(['model_est_period_multiplier', str(model_est_period_multiplier) ] )
        writer.writerow(['model_order', str(model_order) ] )
        writer.writerow(['prob_noise_pow', str(prob_noise_pow) ] )
        writer.writerow(['Nactor', str(Nactor) ] )
        writer.writerow(['pred_step_size_multiplier', str(pred_step_size_multiplier) ] )
        writer.writerow(['buffer_size', str(buffer_size) ] )
        writer.writerow(['stage_obj_struct', str(stage_obj_struct) ] )
        writer.writerow(['R1_diag', str(R1_diag) ] )
        writer.writerow(['R2_diag', str(R2_diag) ] )
        writer.writerow(['Ncritic', str(Ncritic) ] )
        writer.writerow(['gamma', str(gamma) ] )
        writer.writerow(['critic_period_multiplier', str(critic_period_multiplier) ] )
        writer.writerow(['critic_struct', str(critic_struct) ] )
        writer.writerow(['actor_struct', str(actor_struct) ] )   
        writer.writerow(['t [s]', 'x [m]', 'y [m]', 'alpha [rad]', 'stage_obj', 'accum_obj', 'v [m/s]', 'omega [rad/s]'] )

# Do not display annoying warnings when print is on
if is_print_sim_step:
	warnings.filterwarnings('ignore')

my_logger = loggers.Logger3WRobotNI()

#----------------------------------------Main loop
run_curr = 1
datafile = datafiles[0]
        
ros_preset = ROS_preset(ctrl_mode,state_goal=[args.goal_pose_x, args.goal_pose_y,args.goal_pose_theta],
                        state_init=state_init,
                        my_sys=my_sys,
                        my_ctrl_nominal=my_ctrl_nominal,
                        my_ctrl_benchmarking=my_ctrl_benchm,
                        my_logger=my_logger,
                        datafile=datafiles
                        )
ros_preset.spin(is_print_sim_step=args.is_print_sim_step, is_log_data=args.is_log_data)