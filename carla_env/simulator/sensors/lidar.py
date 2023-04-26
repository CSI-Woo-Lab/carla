import carla
from typing_extensions import override

from carla_env.simulator.actor import Actor
from carla_env.simulator.sensors.sensor import Sensor
from carla_env.simulator.simulator import Simulator
from utils.config import ExperimentConfigs


class LidarSensor(Sensor):
    def __init__(self, simulator: Simulator, config: ExperimentConfigs):
        self.__upper_fov = config.lidar.upper_fov
        self.__lower_fov = config.lidar.lower_fov
        self.__rotation_frequency = config.lidar.rotation_frequency
        self.__max_range = config.lidar.max_range
        self.__dropoff_general_rate = config.lidar.dropoff_general_rate
        self.__dropoff_intensity_limit = config.lidar.dropoff_intensity_limit
        self.__dropoff_zero_intensity = config.lidar.dropoff_zero_intensity
        self.__points_per_second = config.lidar.points_per_second

        blueprint = simulator.world.blueprint_library.find("sensor.lidar.ray_cast")
        blueprint.set_attribute("upper_fov", str(self.__upper_fov))
        blueprint.set_attribute("lower_fov", str(self.__lower_fov))
        blueprint.set_attribute("rotation_frequency", str(self.__rotation_frequency))
        blueprint.set_attribute("range", str(self.__max_range))
        blueprint.set_attribute(
            "dropoff_general_rate", str(self.__dropoff_general_rate)
        )
        blueprint.set_attribute(
            "dropoff_intensity_limit", str(self.__dropoff_intensity_limit)
        )
        blueprint.set_attribute(
            "dropoff_zero_intensity", str(self.__dropoff_zero_intensity)
        )
        blueprint.set_attribute("points_per_second", str(self.__points_per_second))

        super().__init__(simulator=simulator, blueprint=blueprint)

    def __get_initial_transform(self):
        return carla.Transform(
            carla.Location(x=1.6, y=0., z=1.7),
            carla.Rotation(pitch=0., yaw=0., roll=0.)
        )

    @override
    def spawn(self, parent: Actor):
        return super().spawn(
            transform=self.__get_initial_transform(),
            parent=parent,
        )

    @property
    def upper_fov(self):
        """The upper field of view of the sensor."""
        return self.__upper_fov
    
    @property
    def lower_fov(self):
        """The lower field of view of the sensor."""
        return self.__lower_fov
    
    @property
    def rotation_frequency(self):
        """The rotation frequency of the sensor."""
        return self.__rotation_frequency
    
    @property
    def max_range(self):
        """The maximum range of the sensor."""
        return self.__max_range
    
    @property
    def dropoff_general_rate(self):
        """The dropoff general rate of the sensor."""
        return self.__dropoff_general_rate
    
    @property
    def dropoff_intensity_limit(self):
        """The dropoff intensity limit of the sensor."""
        return self.__dropoff_intensity_limit
    
    @property
    def dropoff_zero_intensity(self):
        """The dropoff zero intensity of the sensor."""
        return self.__dropoff_zero_intensity
    
    @property
    def points_per_second(self):
        """The points per second of the sensor."""
        return self.__points_per_second