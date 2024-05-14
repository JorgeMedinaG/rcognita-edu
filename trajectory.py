import numpy as np
import math

class TrajectoryGenerator:

        def __init__(self, x_init, y_init) -> None:
            self.way_points = self._generate_trajectory(x_init,y_init,29)
            self.last_way_point = 1

        def _generate_trajectory(self,x_0, y_0, n):
            # x = np.linspace(-5, 5, n)
            # y =( np.power(x,3)  + -15*x - 8)/15
            # x, y = self._lemniscate_trajectory(n)
            x = np.linspace(x_0,0, n)

            error_x = np.linspace(0, math.pi*2, n)
            error_y = np.sin(error_x) 

            m = (y_0/x_0)
            y = m * x + error_y
            theta = np.zeros(n)
            for i in range(1,n):
                theta[i] = np.arctan2( y[i] - y[i-1],x[i] - x[i-1])
            return [x,y,theta]

        def get_nearest_waypoint(self, x, y):
            dist = np.sqrt(np.power(x - self.way_points[0],2) + np.power(y - self.way_points[1], 2))
            index = np.argmin(dist)
            # delta_x = np.absolute(x - self.way_points[0][self.last_way_point])
            # delta_y = np.absolute(y - self.way_points[1][self.last_way_point])
            if (index < self.last_way_point):
                 index = self.last_way_point
            # if (delta_x < 0.1 and delta_y < 0.1):
            #      index = self.last_way_point + 1
            #      self.last_way_point = self.last_way_point + 1
            # else :
            #      index = self.last_way_point
            print("Nearest waypoint index: ")
            print(index)
            print([self.way_points[0][index],self.way_points[1][index],self.way_points[2][index]])
            return [self.way_points[0][index],self.way_points[1][index],self.way_points[2][index]]
        
        def _origin_trajectory(self, x_0, y_0, n ):
            x = np.linspace(x_0,0, n)

            error_x = np.linspace(0, math.pi*2, n)
            error_y = np.sin(error_x) 

            m = (y_0/x_0)
            y = m * x + error_y

        def _lemniscate_trajectory(self, n ):
            t = np.linspace(0,np.pi*2, n)
            a = 10
            x = (a*np.sqrt(2)*np.cos(t)) / (np.sin(t) ** 2 + 1)
            y = (a*np.sqrt(2)*np.cos(t)*np.sin(t)) / (np.sin(t) ** 2 + 1)
            return [x,y]

        