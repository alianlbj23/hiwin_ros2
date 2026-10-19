import math

import pytest
from hiwin_user_py.move_demo import build_goal


def test_goal_carries_joint_constraints_and_scaling():
    goal = build_goal(
        "manipulator",
        {"joint_1": 0.0, "joint_5": -1.5},
        execute=False,
        velocity_scaling=0.1,
        acceleration_scaling=0.2,
    )
    req = goal.request
    assert req.group_name == "manipulator"
    assert req.start_state.is_diff is True
    assert math.isclose(req.max_velocity_scaling_factor, 0.1)
    assert math.isclose(req.max_acceleration_scaling_factor, 0.2)
    assert len(req.goal_constraints) == 1
    jcs = {jc.joint_name: jc.position for jc in req.goal_constraints[0].joint_constraints}
    assert jcs == {"joint_1": 0.0, "joint_5": -1.5}
    assert goal.planning_options.plan_only is True


def test_execute_flag_disables_plan_only():
    goal = build_goal(
        "manipulator", {"joint_1": 0.1}, execute=True, velocity_scaling=0.1, acceleration_scaling=0.1
    )
    assert goal.planning_options.plan_only is False


@pytest.mark.parametrize("vel,acc", [(0.0, 0.1), (1.5, 0.1), (0.1, 0.0), (0.1, -1.0)])
def test_rejects_out_of_range_scaling(vel, acc):
    with pytest.raises(ValueError):
        build_goal(
            "manipulator", {"joint_1": 0.0}, execute=False, velocity_scaling=vel, acceleration_scaling=acc
        )


def test_rejects_empty_joint_positions():
    with pytest.raises(ValueError):
        build_goal("manipulator", {}, execute=False, velocity_scaling=0.1, acceleration_scaling=0.1)
