import carla
import gym
import gym.spaces
import numpy as np

from carla_env.envs.base import BaseCarlaEnv
from utils.cart import cart2pol
from utils.sensors import CollisionSensor, LaneInvasionSensor


class BCCarlaEnv(BaseCarlaEnv):
    def _init(self):
        # dummy variables, to match deep mind control's APIs
        self.action_space = gym.spaces.Box(shape=(2,), low=-1, high=1)
        self.observation_space = gym.spaces.Dict(
            {
                "obs": gym.spaces.Box(shape=(105,), low=-1, high=1),
                "task": gym.spaces.Box(shape=(12,), low=0, high=1),
                "module_select": gym.spaces.Box(shape=(36,), low=0, high=1),
            }
        )
        # roaming carla agent
        self.timesteps = 0
        self.world.tick()

        self.collision_sensor = CollisionSensor(self.vehicle)
        self.lane_invasion_sensor = LaneInvasionSensor(self.vehicle, self)
        self.actor_list.append(self.collision_sensor)
        self.actor_list.append(self.lane_invasion_sensor)

        self.lane_invasion = None

    def reset_init(self):
        super().reset_init()
        self.lane_invasion_sensor.sensor.stop()
        self.lane_invasion_sensor.sensor.destroy()
        self.collision_sensor.sensor.stop()
        self.collision_sensor.sensor.destroy()
        self.collision_sensor = CollisionSensor(self.vehicle)
        self.lane_invasion_sensor = LaneInvasionSensor(self.vehicle, self)
        self.lane_invasion = None

    def reset(self):
        self.reset_init()
        return super().reset()

    def goal_reaching_reward(self, vehicle):
        colhist = self.collision_sensor.get_collision_history()
        lane_invasion = self.lane_invasion
        if lane_invasion is None:
            lane_invasion = {}
        lane_done = (
            colhist
            or carla.libcarla.LaneMarkingType.Solid in lane_invasion
            or carla.libcarla.LaneMarkingType.SolidSolid in lane_invasion
        )

        dist = self.get_distance_vehicle_target(vehicle)

        total_reward, reward_dict, done_dict = super().goal_reaching_reward(vehicle)

        done_dict = {
            "lane_collision_done": lane_done,
            "dist_done": dist < 15,
            **done_dict,
        }
        return total_reward, reward_dict, done_dict

    def _simulator_step(self, action, traffic_light_color=None):
        expert_action = self.compute_action()[0]

        if action is None:
            throttle, steer, brake = 0.0, 0.0, 0.0
        else:
            steer = float(action[1])
            if action[0] >= 0.0:
                throttle = float(action[0])
                brake = 0.0
            else:
                throttle = 0.0
                brake = float(action[0])

            vehicle_control = carla.VehicleControl(
                throttle=throttle,  # [0,1]
                steer=steer,  # [-1,1]
                brake=brake,  # [0,1]
                hand_brake=False,
                reverse=False,
                manual_gear_shift=False,
            )

            self.vehicle.apply_control(vehicle_control)

        # Advance the simulation and wait for the data.
        _, lidar_sensor = self.sync_mode.tick(timeout=10.0)

        # Format rl lidar
        lidar = np.frombuffer(lidar_sensor.raw_data, dtype=np.float32).reshape((-1, 4))

        # (x,y,z) to (min_dist,theta,z)
        lidar_xy = lidar[:, :2]
        lidar_z = lidar[:, 2]

        lidar_xy_cart2pol = np.array(
            list(map(lambda x: cart2pol(x[0], x[1]), lidar_xy))
        )
        lidar_z = np.expand_dims(lidar_z, axis=1)
        lidar_cylinder = np.concatenate((lidar_xy_cart2pol, lidar_z), axis=1)

        lidar_bin = []
        empty_cnt = 0
        # discretize theta
        for i in range(-1 * int(self.num_theta_bin / 2), int(self.num_theta_bin / 2)):
            low_deg = 2 * i * np.pi / self.num_theta_bin
            high_deg = 2 * (i + 1) * np.pi / self.num_theta_bin
            points = lidar_cylinder[
                (lidar_cylinder[:, 1] > low_deg) * (lidar_cylinder[:, 1] < high_deg)
            ][:, 0]

            if not points.any():
                # print(f'{i} ~ {i+1} bin is empty')
                empty_cnt += 1
                lidar_bin.append(np.array([self.range]))
            else:
                max_idx = points.argmax()  # standard (x,y) or (x,y,z)
                lidar_bin.append(
                    lidar_cylinder[
                        (lidar_cylinder[:, 1] > low_deg)
                        * (lidar_cylinder[:, 1] < high_deg)
                    ][max_idx][0]
                )

        reward, reward_dict, done_dict = self.goal_reaching_reward(self.vehicle)
        self.count += 1

        acceleration = self.vehicle.get_acceleration()
        velocity = self.vehicle.get_velocity()
        angular_velocity = self.vehicle.get_angular_velocity()
        location = self.vehicle.get_location()
        rotation = self.vehicle.get_transform().rotation
        forward_vector = rotation.get_forward_vector()

        next_obs = {
            "lidar": np.array(lidar_bin),
            "control": np.array([throttle, steer, brake]),
            "acceleration": np.array([acceleration.x, acceleration.y, acceleration.z]),
            "veolcity": np.array([velocity.x, velocity.y, velocity.z]),
            "angular_veolcity": np.array(
                [angular_velocity.x, angular_velocity.y, angular_velocity.z]
            ),
            "location": np.array([location.x, location.y, location.z]),
            "rotation": np.array([rotation.pitch, rotation.yaw, rotation.roll]),
            "forward_vector": np.array(
                [forward_vector.x, forward_vector.y, forward_vector.z]
            ),
            "target_location": np.array(
                [
                    self.target_location.x,
                    self.target_location.y,
                    self.target_location.z,
                ]
            ),
        }

        done = self.count >= self.max_episode_steps
        if done:
            print(
                f"Episode success: I've reached the episode horizon "
                f"({self.max_episode_steps})."
            )

        info = {
            **{f"reward_{key}": value for key, value in reward_dict.items()},
            **{f"done_{key}": value for key, value in done_dict.items()},
            "control_repeat": self.frame_skip,
            "weather": self.weather,
            "settings_map": self.map.name,
            "settings_multiagent": self.multiagent,
            "traffic_lights_color": "UNLABELED",
            "reward": reward,
            "expert_action": np.array(
                [
                    expert_action.throttle - expert_action.brake,
                    expert_action.steer,
                ],
                dtype=np.float64,
            ),
        }

        next_obs_sensor = np.hstack(
            [value for key, value in next_obs.items() if key != "image"]
        )

        # next_obs_sensor = next_obs_sensor
        task = np.zeros(12)
        task[self.route] = 1
        return (
            {
                "obs": next_obs_sensor,
                "task": task,
                "module_select": np.ones(36),
            },
            reward,
            done or any(done_dict.values()),
            info,
        )
