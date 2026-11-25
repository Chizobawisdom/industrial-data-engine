import numpy as np

# Fixed seed for reproducible simulations
SEED = 42
np.random.seed(SEED)


def cycle_time(mean_log, sigma_log):
    """Log-normal cycle time — right-skewed, realistic for manufacturing."""
    return float(np.random.lognormal(mean=mean_log, sigma=sigma_log))


def repair_duration(mean_log, sigma_log):
    """Log-normal repair duration."""
    return float(np.random.lognormal(mean=mean_log, sigma=sigma_log))


def time_to_failure(shape, scale):
    """Weibull time-to-failure (industry standard for reliability)."""
    return float(scale * np.random.weibull(shape))


def compute_delay_with_breakdown(base_delay, failure_shape, failure_scale,
                                  repair_mean_log, repair_sigma_log):
    """
    Given a base cycle time, decide whether a breakdown occurs during it.

    P(fail during window t) = 1 - exp(-(t/scale)^shape)   [Weibull CDF]

    Returns:
        (total_delay, breakdown_occurred, downtime)
    """
    p_fail = 1.0 - np.exp(-((base_delay / failure_scale) ** failure_shape))
    if np.random.random() < p_fail:
        down = repair_duration(repair_mean_log, repair_sigma_log)
        return base_delay + down, True, down
    return base_delay, False, 0.0


def defect_roll(base_prob):
    """Conditional failure probability."""
    return np.random.random() < base_prob