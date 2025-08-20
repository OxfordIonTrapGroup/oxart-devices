from pipython import GCSDevice, pitools
import numpy as np
from numpy import sin,cos,pi
import pickle
import xml.etree.ElementTree as ET

class Calculations:
    def rotate_around_vector(self, v: np.ndarray, k: np.ndarray, q: float):
        """rotates v around k by angle q (in radians)"""
        # renormalise k
        k_unit = k / np.linalg.norm(k)

        # apply rodriguez formula
        kxv = np.cross(k_unit,v)
        kxkxv = np.cross(k_unit,kxv)
        v_rot_k = v + sin(q)*kxv + (1-cos(q))*kxkxv
        
        return v_rot_k

    def chain_coordinate_axes(self, offset_coords: list[float], initial_axes: list[np.ndarray]):
        """finds the coordinate axes for a new CS linked to an old CS with coordinate axes initial_axes by offsets offset_coords"""
        """all axes are defined in the hexapod's default ZERO CS relative to the original pivot point"""
        """offset_coords must be a list of floats in the form [X,Y,Z,U,V,W] for axes offsets of new CS with respect to old CS"""
        """must provide X,Y,Z in mm and U,V,W in degrees"""
        """initial_axes must be a length-4 list of 3x1 numpy arrays of floats for the offset (in mm) and 3-directions (normalised) of the initial CS axes in the form [O,R,S,T]"""
        # load, convert to radians and normalise axes
        X, Y, Z, U, V, W = offset_coords.copy()
        U *= pi/180
        V *= pi/180
        W *= pi/180
        O, R, S, T = [x.copy() for x in initial_axes]
        R /= np.linalg.norm(R)
        S /= np.linalg.norm(S)
        T /= np.linalg.norm(T)

        # define final offset
        O_final = O + X*R + Y*S + Z*T

        # rotate axes around R
        R_rot_R = R
        S_rot_R = self.rotate_around_vector(S, R, U)
        T_rot_R = self.rotate_around_vector(T, R, U)

        # rotate around once-rotated S
        R_rot_RS = self.rotate_around_vector(R_rot_R, S_rot_R, V)
        S_rot_RS = S_rot_R
        T_rot_RS = self.rotate_around_vector(T_rot_R, S_rot_R, V)

        # rotate axes around twice-rotated T
        R_rot_RST = self.rotate_around_vector(R_rot_RS, T_rot_RS, W)
        S_rot_RST = self.rotate_around_vector(S_rot_RS, T_rot_RS, W)
        T_rot_RST = T_rot_RS
        
        return [O_final, R_rot_RST, S_rot_RST, T_rot_RST]

    def position_at_home(self, position: np.ndarray, work_axes: list[np.ndarray], tool_axes: list[np.ndarray]):
        """takes a position relative to the hexapod's default pivot point in ZERO CS to calculate where that point is in the same CS when the system is 'homed' in a work tool system with the provided axes"""
        """position must be a 3x1 numpy array of floats"""
        """work_axes must be a length-4 list of 3x1 numpy arrays of floats for the offset (in mm) and 3-directions (normalised) of the WORK axes with respect to the hexapod's default pivot point in ZERO CS in the form [O,R,S,T]"""
        """tool_axes must be a length-4 list of 3x1 numpy arrays of floats for the offset (in mm) and 3-directions (normalised) of the WORK axes with respect to the hexapod's default pivot point in ZERO CS in the form [o,r,s,t]"""

        # copy the given axes and renormalise
        O, R, S, T = [x.copy() for x in work_axes]
        R /= np.linalg.norm(R)
        S /= np.linalg.norm(S)
        T /= np.linalg.norm(T)
        o, r, s, t = [x.copy() for x in tool_axes]
        r /= np.linalg.norm(r)
        s /= np.linalg.norm(s)
        t /= np.linalg.norm(t)

        # find position in initial tool coordinate system
        r0 = np.dot(position - o, r)
        s0 = np.dot(position - o, s)
        t0 = np.dot(position - o, t)

        # find and return position in real space when homed
        position_homed = O + r0*R + s0*S + t0*T

        return position_homed

    def move_abs_position(self, position: np.ndarray, target_abs_coords: list[float], work_axes: list[np.ndarray], tool_axes: list[np.ndarray]):
        """takes a position relative to hexapod's default pivot point in ZERO CS to calculate new position relative to hexapod's default pivot point in ZERO CS after a MOV command"""
        """position must be a 3x1 numpy array of floats"""
        """target_abs_coords must be a list of floats in the form [X,Y,Z,U,V,W] for the MOV command"""
        """must provide X,Y,Z in mm and U,V,W in degrees"""
        """work_axes must be a length-4 list of 3x1 numpy arrays of floats for the offset (in mm) and 3-directions (normalised) of the WORK axes with respect to the hexapod's default pivot point in ZERO CS in the form [O,R,S,T]"""
        """tool_axes must be a length-4 list of 3x1 numpy arrays of floats for the offset (in mm) and 3-directions (normalised) of the WORK axes with respect to the hexapod's default pivot point in ZERO CS in the form [o,r,s,t]"""
        # find position in custom CS home
        position_homed = self.position_at_home(position, work_axes, tool_axes)
        
        # load, convert to radians and normalise axes
        X, Y, Z, U, V, W = target_abs_coords.copy()
        U *= pi/180
        V *= pi/180
        W *= pi/180
        O, R, S, T = [x.copy() for x in work_axes]
        R /= np.linalg.norm(R)
        S /= np.linalg.norm(S)
        T /= np.linalg.norm(T)

        # prepare initial position for rotation
        position_deviation = position_homed - O

        # rotate position and axes around R
        position_rot_R = self.rotate_around_vector(position_deviation, R, U)
        S_rot_R = self.rotate_around_vector(S, R, U)
        T_rot_R = self.rotate_around_vector(T, R, U)

        # rotate position and axes around once-rotated S
        position_rot_RS = self.rotate_around_vector(position_rot_R, S_rot_R, V)
        T_rot_RS = self.rotate_around_vector(T_rot_R, S_rot_R, V)

        # rotate position and axes around twice-rotated T
        position_rot_RST = self.rotate_around_vector(position_rot_RS, T_rot_RS, W)

        # reshift to get final position
        position_final = position_rot_RST + O + X*R + Y*S + Z*T

        return position_final

    def move_rel_position(self, position: np.ndarray, current_abs_coords: list[float], target_rel_coords: list[float], work_axes: list[np.ndarray], tool_axes: list[np.ndarray]):
        """takes a position relative to hexapod's default pivot point in ZERO CS to calculate new position relative to hexapod's default pivot point in ZERO CS after an MVR command"""
        """position must be a 3x1 numpy array of floats"""
        """current_abs_coords must be a list of floats in the form [X,Y,Z,U,V,W] for current position in custom coordinate system"""
        """target_rel_coords must be a list of floats in the form [dX,dY,dZ,dU,dV,dW] for target relative position in custom coordinate system"""
        """must provide X,Y,Z,dX,dY,dZ in mm and U,V,W,dU,dV,dW in degrees"""
        """work_axes must be a length-4 list of 3x1 numpy arrays of floats for the offset (in mm) and 3-directions (normalised) of the WORK axes with respect to the hexapod's default pivot point in ZERO CS in the form [O,R,S,T]"""
        """tool_axes must be a length-4 list of 3x1 numpy arrays of floats for the offset (in mm) and 3-directions (normalised) of the TOOL axes with respect to the hexapod's default pivot point in ZERO CS in the form [o,r,s,t]"""
        # combine current and relative coordinates
        final_abs_coords = [a+b for a,b in zip(current_abs_coords, target_rel_coords)]
        # apply the move to absolute position script
        position_final = self.move_abs_position(position, final_abs_coords, work_axes, tool_axes)

        return position_final

    def move_work_position(self, position: np.ndarray, current_abs_coords: list[float], target_work_coords: list[float], work_axes: list[np.ndarray], tool_axes: list[np.ndarray]):
        """takes a position relative to hexapod's default pivot point in ZERO CS to calculate new position relative to hexapod's default pivot point in ZERO CS after an MRW command"""
        """position must be a 3x1 numpy array of floats"""
        """current_abs_coords must be a list of floats in the form [X,Y,Z,U,V,W] for current position in custom coordinate system"""
        """target_work_coords must be a list of floats in the form [dX,dY,dZ,dU,dV,dW] for target relative position in custom coordinate system"""
        """must provide X,Y,Z,dX,dY,dZ in mm and U,V,W,dU,dV,dW in degrees"""
        """work_axes must be a length-4 list of 3x1 numpy arrays of floats for the offset (in mm) and 3-directions (normalised) of the WORK axes with respect to the hexapod's default pivot point in ZERO CS in the form [O,R,S,T]"""
        """tool_axes must be a length-4 list of 3x1 numpy arrays of floats for the offset (in mm) and 3-directions (normalised) of the TOOL axes with respect to the hexapod's default pivot point in ZERO CS in the form [o,r,s,t]"""
        # find current position of critical point
        position_current = self.move_abs_position(position, current_abs_coords, work_axes, tool_axes)

        # load, convert to radians and normalise axes
        X, Y, Z, U, V, W = target_work_coords.copy()
        U *= pi/180
        V *= pi/180
        W *= pi/180
        O, R, S, T = [x.copy() for x in work_axes]
        R /= np.linalg.norm(R)
        S /= np.linalg.norm(S)
        T /= np.linalg.norm(T)

        # compute deviation from pivot point
        position_deviation = position_current - O

        # translate along R,S,T by X,Y,Z then rotate around fixed R,S,T by U,V,W
        position_shifted = position_deviation + X*R + Y*S + Z*T
        position_rot_R = self.rotate_around_vector(position_shifted, R, U)
        position_rot_RS = self.rotate_around_vector(position_rot_R, S, V)
        position_rot_RST = self.rotate_around_vector(position_rot_RS, T, W)

        # add back initial offset and return position
        position_final = position_rot_RST + O
        
        return position_final

    def move_tool_position(self, position: np.ndarray, current_abs_coords: list[float], target_tool_coords: list[float], work_axes: list[np.ndarray], tool_axes: list[np.ndarray]):
        """takes a position relative to hexapod's default pivot point in ZERO CS to calculate new position relative to hexapod's default pivot point in ZERO CS after an MRW command"""
        """position must be a 3x1 numpy array of floats"""
        """current_abs_coords must be a list of floats in the form [X,Y,Z,U,V,W] for current position in custom coordinate system"""
        """target_work_coords must be a list of floats in the form [dX,dY,dZ,dU,dV,dW] for target relative position in custom coordinate system"""
        """must provide X,Y,Z,dX,dY,dZ in mm and U,V,W,dU,dV,dW in degrees"""
        """work_axes must be a length-4 list of 3x1 numpy arrays of floats for the offset (in mm) and 3-directions (normalised) of the WORK axes with respect to the hexapod's default pivot point in ZERO CS in the form [O,R,S,T]"""
        """tool_axes must be a length-4 list of 3x1 numpy arrays of floats for the offset (in mm) and 3-directions (normalised) of the TOOL axes with respect to the hexapod's default pivot point in ZERO CS in the form [o,r,s,t]"""
        # find current position of critical point
        position_current = self.move_abs_position(position, current_abs_coords, work_axes, tool_axes)

        # find current position of tool axes
        o, r, s, t = self.chain_coordinate_axes(current_abs_coords, work_axes)
        r /= np.linalg.norm(r)
        s /= np.linalg.norm(s)
        t /= np.linalg.norm(t)

        # load and convert target coords to radians
        X, Y, Z, U, V, W = target_tool_coords.copy()
        U *= pi/180
        V *= pi/180
        W *= pi/180

        # compute deviation from pivot point
        position_deviation = position_current - o

        # rotate position and axes around r
        position_rot_r = self.rotate_around_vector(position_deviation, r, U)
        s_rot_r = self.rotate_around_vector(s, r, U)
        t_rot_r = self.rotate_around_vector(t, r, U)

        # rotate position and axes around once-rotated s
        position_rot_rs = self.rotate_around_vector(position_rot_r, s_rot_r, V)
        t_rot_rs = self.rotate_around_vector(t_rot_r, s_rot_r, V)

        # rotate position and axes around twice-rotated T
        position_rot_rst = self.rotate_around_vector(position_rot_rs, t_rot_rs, W)

        # reshift to get final position
        position_final = position_rot_rst + o + X*r + Y*s + Z*t

        return position_final
    
    def read_safety_data(self, safety_case: str = None, safety_data: list[float] = []):
        """defines how the safety data should be unpacked"""
        match safety_case:
            case None:
                safety_parameters = []
            case 'rectangle':
                """the safety_data should be a list of length 15 with contents in this order:
                    coordinates of origin, direction of rectangle's x-axis, direction of rectangle's y-axis,
                    safety bounds in x-direction, safety bounds in y-direction, safety bounds in z-direction.
                    (all points, directions and distances measured in hexapod's native coordinate system)
                    
                    as such the list should contain the numbers:
                    [origin_x, origin_y, origin_z, x_axis_x, x_axis_y, x_axis_z, y_axis_x, y_axis_y, y_axis_z,
                     lower_bound_x, upper_bound_x, lower_bound_y, upper_bound_y, lower_bound_z, upper_bound_z]
                """
                # x_axis is used as is. only component of y_axis orthogonal to x_axis is used
                # read the origin position
                origin = np.array(safety_data[0:3], dtype=float)
                # read and normalise x-axis
                x_axis = np.array(safety_data[3:6], dtype=float)
                x_axis /= np.linalg.norm(x_axis)
                # read and normalise component of y-axis perpendicular to x-axis
                y_axis = np.array(safety_data[6:9], dtype=float)
                y_axis -= x_axis * np.dot(x_axis, y_axis)
                y_axis /= np.linalg.norm(y_axis)
                # compute z-axis
                z_axis = np.cross(x_axis, y_axis)
                # read the extents from origin along the axes direction in form [-extent, +extent]
                extent_x = safety_data[9:11]
                extent_y = safety_data[11:13]
                extent_z = safety_data[13:15]
                # write safety parameters
                safety_parameters = [origin, x_axis, y_axis, z_axis, extent_x, extent_y, extent_z]
            case 'cylinder':
                """the safety_data should be a list of length 9 with contents in this order:
                    coordinates of origin, direction of cylinder symmetry axis,
                    safety bounds from origin along axis, safety radius of cylinder.
                    (all points, directions and distances measured in hexapod's native coordinate system)
                    
                    as such the list should contain the numbers:
                    [origin_x, origin_y, origin_z, axis_x, axis_y, axis_z,
                     lower_bound_axis, upper_bound_axis, radius]
                """
                # read the origin position
                origin = np.array(safety_data[0:3], dtype=float)
                # read and normalise the cylinder axis
                axis = np.array(safety_data[3:6], dtype=float)
                axis /= np.linalg.norm(axis)
                # read the extents from origin along the cylinder axis in form [-extent, +extent]
                extent_axis = safety_data[6:8]
                # read the radius of the cylinder
                radius = safety_data[8]
                # write the safety parameters
                safety_parameters = [origin, axis, extent_axis, radius]
            case _:
                raise ValueError('Safety case not recognised.')
        return safety_parameters

    def point_in_safety(self, position: np.ndarray, safety_case: str = None, safety_parameters: list = []):
        """checks whether position is inside the safety zone"""
        """the user should add recognised geometry cases and safety functions for their specific experimental setup"""
        match safety_case:
            case None:
                return True
            case 'rectangle':
                return self.check_safety_rectangle(position, safety_parameters)
            case 'cylinder':
                return self.check_safety_cylinder(position, safety_parameters)
            case _:
                raise ValueError('Safety case not recognised.')

    def check_safety_rectangle(self, position: np.ndarray, safety_parameters: list):
        """checks if a point is in safety for the rectangle safety case"""
        origin, x_axis, y_axis, z_axis, extent_x, extent_y, extent_z = safety_parameters
        displacement = position - origin
        safe_x = (extent_x[0] < np.dot(displacement, x_axis) < extent_x[1])
        safe_y = (extent_y[0] < np.dot(displacement, y_axis) < extent_y[1])
        safe_z = (extent_z[0] < np.dot(displacement, z_axis) < extent_z[1])
        return (safe_x and safe_y and safe_z)
    def check_safety_cylinder(self, position: np.ndarray, safety_parameters):
        """checks if a point is in safety for the cylinder safety case"""
        origin, axis, extent_axis, radius = safety_parameters
        displacement = position - origin
        displacement_axis = np.dot(displacement, axis)
        safe_extent = (extent_axis[0] < displacement_axis < extent_axis[1])
        safe_radius = (np.linalg.norm(displacement - axis*displacement_axis) < abs(radius))
        return (safe_extent and safe_radius)


class Hexapod(Calculations):
    """Driver for the Hexpod controller C-887 via serial (COM)"""
    """For Hexapod H811.F2, pivot point sits 12.67mm below top middle of movement plate"""

    def __init__(self, address: str = None, comport: int = None, baudrate: int = None, safety_case: str = None, safety_data: list[float] = [], critical_points_data: list[float] = []):
        self.dev = GCSDevice('C-887')
        # store safety information for later checking
        self.safety_case = safety_case
        float_safety_data = [float(x) for x in safety_data]
        self.safety_parameters = self.read_safety_data(self.safety_case, float_safety_data)
        self.critical_points = []
        count = 0
        while count < len(critical_points_data):
            point = np.array([critical_points_data[count], critical_points_data[count+1], critical_points_data[count+2]], dtype=float)
            self.critical_points.append(point)
            count += 3
        # default to restricted motion mode
        self.motion_restricted = True
        # store list of systems for bookkeeping
        self.systems = []
        # store work and tool axes
        base_axes = [np.array([0,0,0], dtype=float),np.array([1,0,0], dtype=float),np.array([0,1,0], dtype=float),np.array([0,0,1], dtype=float)] 
        self.work_axes = [x.copy() for x in base_axes]
        self.tool_axes = [x.copy() for x in base_axes]

        # connect to the Hexapod controller - defaults to the TCPIP if an address is given
        if address == None: 
            self.dev.ConnectRS232(comport, baudrate)
        else:
            self.dev.ConnectTCPIP(address)
        print('Hexapod connected.')

        # References the stage using the reference position
        pitools.startup(self.dev, stages=None, refmodes='FRF')
        pitools.waitonreferencing(self.dev)

        # activate default coordinate system
        self.activate_default_system()
    
    def toggle_motion_restriction(self):
        """switches to unrestricted motion mode"""
        self.motion_restricted = not self.motion_restricted
        if self.motion_restricted:
            print('Motion restricted...')
        else:
            print('Motion unrestricted...')

    def payload_in_safety(self, critical_points: list[np.ndarray]):
        """checks whether all the critical_points on the payload are inside the safety zone"""
        for point in critical_points:
            if self.point_in_safety(point, self.safety_case, self.safety_parameters):
                continue
            else:
                return 0
        return 1

    def reference(self):
        """FRF: references axes and moves to origin"""
        self.dev.FRF()
        pitools.waitonreferencing(self.dev)

        # Activating zero coordinate system
        self.activate_default_system()
        print('Hexapod ready: {}'.format(self.dev.qIDN().strip()))

    def move_abs(self, axes: list[str], values: list[float]):
        """MOV: Moves the tool to this absolute position in the work coordinate system according to activated coordinates (mm, deg)"""
        """X,Y,Z cause travelling along the fixed work axes while U,V,W cause spinning around the mobile tool axes"""

        # check if movement is allowed
        if self.motion_restricted:
            target = []
            for axis in ['X', 'Y', 'Z', 'U', 'V', 'W']:
                if axis in axes:
                    target.append(values[axes.index(axis)])
                else:
                    target.append(0)
            # calculate new corners of payload envelope
            new_critical_points = [self.move_abs_position(point, target, self.work_axes, self.tool_axes) for point in self.critical_points]
            # check if payload will be in safety
            payload_safe = self.payload_in_safety(new_critical_points)
            if not payload_safe:
                raise ValueError('Movement will cause payload envelope to breach safety envelope and so is not allowed.')

        self.dev.MOV(axes, values)
        pitools.waitontarget(self.dev, axes=self.get_axes())
    
    def move_rel(self, axes: list[str], values: list[float]):
        """MOV: Moves the tool by a relative amount in the work coordinate system according to activated coordinates (mm, deg)"""
        """X,Y,Z cause travelling along the fixed work axes while U,V,W cause spinning around the mobile tool axes"""

        # check if movement is allowed
        if self.motion_restricted:
            target = []
            for axis in ['X', 'Y', 'Z', 'U', 'V', 'W']:
                if axis in axes:
                    target.append(values[axes.index(axis)])
                else:
                    target.append(0)
            # calculate new corners of payload envelope
            current = list(self.get_positions().values())
            new_critical_points = [self.move_rel_position(point, current, target, self.work_axes, self.tool_axes) for point in self.critical_points]
            # check if payload will be in safety
            payload_safe = self.payload_in_safety(new_critical_points)
            if not payload_safe:
                raise ValueError('Movement will cause payload envelope to breach safety envelope and so is not allowed.')

        self.dev.MVR(axes, values)
        pitools.waitontarget(self.dev, axes=self.get_axes())

    def move_work(self, axes: list[str], values: list[float]):
        """MRW: Moves the tool by a relative amount in the work coordinate system according to activated coordinates (mm, deg)"""
        """X,Y,Z cause travelling along the fixed work axes (like MOV/MVR) and U,V,W cause swinging around the fixed work axes (unlike MOV/MVR)"""
        """command only accessible in an active work tool system"""

        # check if movement is allowed
        if self.motion_restricted:
            target = []
            for axis in ['X', 'Y', 'Z', 'U', 'V', 'W']:
                if axis in axes:
                    target.append(values[axes.index(axis)])
                else:
                    target.append(0)
            # calculate new corners of payload envelope
            current = list(self.get_positions().values())
            new_critical_points = [self.move_work_position(point, current, target, self.work_axes, self.tool_axes) for point in self.critical_points]
            # check if payload will be in safety
            payload_safe = self.payload_in_safety(new_critical_points)
            if not payload_safe:
                raise ValueError('Movement will cause payload envelope to breach safety envelope and so is not allowed.')
    
        self.dev.MRW(axes, values)
        pitools.waitontarget(self.dev, axes=self.get_axes())

    def move_tool(self, axes: list[str], values: list[float]):
        """MRT: Moves the tool by a relative amount in the tool coordinate system according to activated coordinates (mm, deg)"""
        """X,Y,Z cause gliding along the mobile tool axes (unlike MOV/MVR) and U,V,W cause spinning around the mobile tool axes (like MOV/MVR)"""
        """command only accessible in an active work tool system"""

        # check if movement is allowed
        if self.motion_restricted:
            target = []
            for axis in ['X', 'Y', 'Z', 'U', 'V', 'W']:
                if axis in axes:
                    target.append(values[axes.index(axis)])
                else:
                    target.append(0)
            # calculate new corners of payload envelope
            current = list(self.get_positions().values())
            new_critical_points = [self.move_tool_position(point, current, target, self.work_axes, self.tool_axes) for point in self.critical_points]
            # check if payload will be in safety
            payload_safe = self.payload_in_safety(new_critical_points)
            if not payload_safe:
                raise ValueError('Movement will cause payload envelope to breach safety envelope and so is not allowed.')

        self.dev.MRT(axes, values)
        pitools.waitontarget(self.dev, axes=self.get_axes())

    def home(self, axes: list[str] = ['X', 'Y', 'Z', 'U', 'V', 'W']):
        """Move the specified axes of the hexapod to home position"""
        num = len(axes)
        self.move_abs(axes, [0]*num)
        print("The following axes were successfully homed: " + str(axes))

    def move_to_current(self):
        current_coords = list(self.get_positions().values())
        self.dev.MOV(['X', 'Y', 'Z', 'U', 'V', 'W'], current_coords)
        pitools.waitontarget(self.dev, axes=self.get_axes())

    def set_velocity(self, velocity=5):
        """VLS: Set velocity mm/s"""
        self.dev.VLS(velocity)

    def get_active_coordinate_system(self):
        """qKEN: Gets current CS"""
        return self.dev.qKEN()
    
    def get_active_coordinate_system_names(self):
        """gets the name of the current systems from qKEN response"""
        tool_name = 'ZERO'
        work_name = 'ZERO'
        
        current_systems = self.get_active_coordinate_system()
        for name, ctype in current_systems.items():
            if ctype == 'KST':  # TOOL system
                tool_name = name
            elif ctype == 'KSW':  # WORK system
                work_name = name
                
        return work_name, tool_name
    
    def get_all_coordinate_systems(self):
        """qKLS: Gets properties of all CS's"""
        return self.dev.qKLS()
    
    def get_coordinate_system_chain(self, name):
        """gets the parent relationships for a specific system back to ZERO"""
        """displays in the form [(PARENT, [OFFSETS_of_name_from_parent]), (GRANDPARENT, [OFFSETS_of_parent_from_grandparent]), ...]"""
        # get the xml style string of system details
        xml_string = self.get_all_coordinate_systems()

        # parse and build lookup
        root = ET.fromstring(xml_string)
        system_details = {elem.attrib['Name']: elem for elem in root}

        chain   = []
        current = name

        # loop until we reach ZERO or run out of valid systems
        if current not in system_details:
            raise ValueError('Requested coordinate system does not exist.')
        while current in system_details and current != 'ZERO':
            elem = system_details[current]
            parent = elem.attrib['Parent']
            pos_elem = elem.find('POS')

            # gather offsets in X,Y,Z,U,V,W order
            offsets = [float(pos_elem.attrib[k]) for k in ('X','Y','Z','U','V','W')]

            chain.append((parent, offsets))
            current = parent

        chain.reverse()
        return chain

    def define_work_coordinate_system(self, name: str, axes: list[str], offsets: list[float]):
        """KSW: Defines a 'work' CS named `name` with given offsets (mm or deg)"""
        self.dev.KSW(name, axes, offsets)
        print(f"{name} work system created with offsets {dict(zip(axes, offsets))}.")
        # appends active list of custom systems
        if name not in self.systems:
            self.systems.append(name)
    
    def define_tool_coordinate_system(self, name: str, axes: list[str], offsets: list[float]):
        """KSW: Defines a 'tool' CS named `name` with given offsets (mm or deg)"""
        self.dev.KST(name, axes, offsets)
        print(f"{name} tool system created with offsets {dict(zip(axes, offsets))}.")
        # appends active list of custom systems
        if name not in self.systems:
            self.systems.append(name)

    def link_coordinate_systems(self, successor: str, predecessor: str):
        """KLN: Links a one coordinate system as the successor to another"""
        self.dev.KLN(successor, predecessor)
        print(successor + " system linked as successor to " + predecessor + " system.")

    def define_beam_camera_set(self, BEAM: str, BEAM_UNPIVOTED: str, BEAM_UNCENTRED: str, 
                               CAMERA: str, CAMERA_UNPIVOTED: str, CAMERA_UNORIENTED: str, 
                               frame_definition: list[list[float]]):
        """defines a three piece successor-predecessor work CS chain called BEAM, BEAM_UNPIVOTED and BEAM_UNSHIFTED respectively"""
        """BEAM_UNCENTRED and ZERO differ by a V then W rotation"""
        """BEAM_UNPIVOTED and BEAM_UNCENTRED differ by a YZ shift"""
        """BEAM and BEAM_UNPIVOTED differ by an XYZ shift"""

        """defines a three piece successor-predecessor tool CS chain called CAMERA, CAMERA_UNPIVOTED and CAMERA_UNORIENTED respectively"""
        """CAMERA_UNORIENTED and ZERO differ by a V then W rotation"""
        """CAMERA_UNPIVOTED and CAMERA_UNORIENTED differ by a U rotation"""
        """CAMERA and CAMERA_UNPIVOTED differ by the same XYZ shift as between BEAM and BEAM_UNPIVOTED"""

        """systems is a list of current custom coordinate systems, for bookkeeping"""
        """frame_definitions is a list of lists of rotations and translations in the form"""
        """[[dV_beam, dW_beam, dY_beam, dZ_beam], [dV_camera, dW_camera, dU_camera], [dX_both, dY_both, dZ_both]]"""
        """the offsets are explicitly defined in the order above since the hexapod natively applies X>Y>Z>U>V>W"""
        [dV_beam, dW_beam, dY_beam, dZ_beam], [dV_camera, dW_camera, dU_camera], [dX_both, dY_both, dZ_both] = frame_definition

        # define and link the work systems
        self.define_work_coordinate_system(BEAM_UNCENTRED, ['V', 'W'], [dV_beam, dW_beam])
        self.define_work_coordinate_system(BEAM_UNPIVOTED, ['Y', 'Z'], [dY_beam, dZ_beam])
        self.link_coordinate_systems(BEAM_UNPIVOTED, BEAM_UNCENTRED)
        self.define_work_coordinate_system(BEAM, ['X', 'Y', 'Z'], [dX_both, dY_both, dZ_both])
        self.link_coordinate_systems(BEAM, BEAM_UNPIVOTED)

        # define and link the tool systems
        self.define_tool_coordinate_system(CAMERA_UNORIENTED, ['V', 'W'], [dV_camera, dW_camera])
        self.define_tool_coordinate_system(CAMERA_UNPIVOTED, ['U'], [dU_camera])
        self.link_coordinate_systems(CAMERA_UNPIVOTED, CAMERA_UNORIENTED)
        self.define_tool_coordinate_system(CAMERA, ['X', 'Y', 'Z'], [dX_both, dY_both, dZ_both])
        self.link_coordinate_systems(CAMERA, CAMERA_UNPIVOTED)

    def load_and_define_iterated_beam_camera_set(self, iterations: int, pathname: str, filename: str, 
                                                                 work: str = 'BEAM', tool: str = 'CAMERA'):
        """looks into ./alignmentBeamCamera/pathname/filename_i.pk for frame definition numbers, with i being 1,2,...,iterations"""
        """defines a composite frame from these frame definitions"""
        frame_definitions = []

        # iterate through prior iterations to load system
        for i in np.arange(1, iterations+1):
            # load the frame definition numbers
            with open('./alignmentBeamCamera/' + pathname + '/' + filename + '_' + str(i) + '.pk', 'rb') as fi:
                frame_definitions.append(pickle.load(fi))

            # define a coordinate system from each iteration
            self.define_beam_camera_set(work+'_'+str(i), work+'_UNPIVOTED_'+str(i), work+'_UNCENTRED_'+str(i), 
                                                                  tool+'_'+str(i), tool+'_UNPIVOTED_'+str(i), tool+'_UNORIENTED_'+str(i), 
                                                                  frame_definitions[i-1])
            # chain each iteration on the prior
            if i == 1:
                continue
            self.link_coordinate_systems(work+'_UNCENTRED_'+str(i), work+'_'+str(i-1))
            self.link_coordinate_systems(tool+'_UNORIENTED_'+str(i), tool+'_'+str(i-1))

    def activate_coordinate_system(self, name: str = 'ZERO'):
        """KEN: Activate coordinate system with given name"""
        """activating a coordinate system also updates the current work and tool axes definitions"""
        self.dev.KEN(name)
        self.move_to_current()

        # get current CS names and chains
        current_work_name, current_tool_name = self.get_active_coordinate_system_names()
        work_chain = self.get_coordinate_system_chain(current_work_name)
        tool_chain = self.get_coordinate_system_chain(current_tool_name)

        # reset the work and tool axes definitions
        base_axes = [np.array([0,0,0], dtype=float),np.array([1,0,0], dtype=float),np.array([0,1,0], dtype=float),np.array([0,0,1], dtype=float)] 
        self.work_axes = [x.copy() for x in base_axes]
        self.tool_axes = [x.copy() for x in base_axes]

        # iterate over work chain definitions to find current axes
        for _, offsets in work_chain:
            self.work_axes = self.chain_coordinate_axes(offsets, self.work_axes)
        # iterate over tool chain definitions to find current axes
        for _, offsets in tool_chain:
            self.tool_axes = self.chain_coordinate_axes(offsets, self.tool_axes)

        print(f"{name} system activated.")

    def activate_default_system(self):
        """KEN: Activate default coordinate system"""
        self.activate_coordinate_system()

    def activate_work_tool_set(self, work: str, tool: str):
        """KEN: Activate work and tool coordinate system with given names (can be 'ZERO')"""
        if tool == 'ZERO':
            self.activate_coordinate_system('ZERO')
            self.activate_coordinate_system(work)
        else:
            self.activate_coordinate_system(work)
            self.activate_coordinate_system(tool)

    def delete_coordinate_system(self, name: str):
        """KRM: Delete coordinate system with given name (cannot be current CS)"""
        self.dev.KRM(name)
        self.systems.remove(name)
        print(f"{name} system deleted.")

    def delete_all_systems(self):
        """switches to default system, deletes listed custom coordinate systems"""
        self.activate_default_system()
        for system in self.systems.copy():
            self.delete_coordinate_system(system)

    def set_lower_soft_limits(self, axes: list[str], values: list[float]):
        """NLM: Set lower soft limits - only in ZERO coordinate system"""
        self.dev.NLM(axes, values)

    def set_upper_soft_limits(self, axes: list[str], values: list[float]):
        """PLM: Set upper soft limits - only in ZERO coordinate system"""
        self.dev.PLM(axes, values)

    def toggle_soft_limits(self, axes: list[str], values: list[bool]):
        """SSL: Activate/deactivate soft limits - only in ZERO coordinate system"""
        self.dev.SSL(axes, values)

    def get_axes(self):
        """Names of axes ['X', 'Y', 'Z', 'U', 'V', 'W']"""
        return self.dev.axes

    def get_positions(self):
        """qPOS: Get current positions in active CS"""
        return self.dev.qPOS()
    
    def get_travel_limits(self):
        maxrange = pitools.getmaxtravelrange(self.dev, None)
        return maxrange

    def close(self):
        self.delete_all_systems()
        self.dev.CloseConnection()
        print('Hexapod closed.')

    def ping(self):
        return True
