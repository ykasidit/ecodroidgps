##### bitmasks: bit offsets

class ln_feature:
    ### LN Feature: uint32
    Instantaneous_Speed_Supported	=	0
    Total_Distance_Supported	=	1
    Location_Supported	=	2
    Elevation_Supported	=	3
    Heading_Supported	=	4
    Rolling_Time_Supported	=	5
    UTC_Time_Supported	=	6
    Remaining_Distance_Supported	=	7
    Remaining_Vertical_Distance_Supported	=	8
    Estimated_Time_of_Arrival_Supported	=	9
    Number_of_Beacons_in_Solution_Supported	=	10
    Number_of_Beacons_in_View_Supported	=	11
    Time_to_First_Fix_Supported	=	12
    Estimated_Horizontal_Position_Error_Supported	=	13
    Estimated_Vertical_Position_Error_Supported	=	14
    Horizontal_Dilution_of_Precision_Supported	=	15
    Vertical_Dilution_of_Precision_Supported	=	16
    Location_and_Speed_Characteristic_Content_Masking_Supported	=	17
    Fix_Rate_Setting_Supported	=	18
    Elevation_Setting_Supported	=	19
    Position_Status_Supported	=	20


class location_and_speed:
    ### location and speed: uint16
    Instantaneous_Speed_Present	=	0
    Total_Distance_Present	=	1
    Location_Present	=	2
    Elevation_Present	=	3
    Heading_Present	=	4
    Rolling_Time_Present	=	5
    UTC_Time_Present	=	6
    Position_Status	=	7
    Speed_and_Distance_format	=	9
    Elevation_Source	=	10
    Heading_Source	=	12
