import simpy
import io
import contextlib
from factorysimpy.nodes.source import Source
from factorysimpy.nodes.machine import Machine
from factorysimpy.nodes.sink import Sink
from factorysimpy.edges.buffer import Buffer
from simulator.distributions import cycle_time, compute_delay_with_breakdown, defect_roll
from simulator.logger import EventLogger

# --- Logging Source and Machine ---
class LoggingSource(Source):
    """A Source that logs when it generates an item."""
    def __init__(self, env, id, logger, **kwargs):
        super().__init__(env, id, **kwargs)
        self.logger = logger

    def _push_item(self, item, *args, **kwargs):
        # Log the ENTRY with the actual item ID
        self.logger.log_production_event(self.env.now, item.id, "SOURCE", "ENTRY")
        
        # Wait for the parent to finish pushing the item to the buffer
        result = yield from super()._push_item(item, *args, **kwargs)
        
        # Log the EXIT with the actual item ID
        self.logger.log_production_event(self.env.now, item.id, "SOURCE", "EXIT")
        return result


class LoggingMachine(Machine):
    """A standard Machine that logs ENTRY and EXIT events for items."""
    def __init__(self, env, id, logger, **kwargs):
        super().__init__(env, id, **kwargs)
        self.logger = logger

    def worker(self, item, processing_delay, req_token):
        self.logger.log_production_event(self.env.now, item.id, self.id, "ENTRY")
        try:
            yield from super().worker(item, processing_delay, req_token)
        finally:
            self.logger.log_production_event(self.env.now, item.id, self.id, "EXIT")


# --- Custom Machines ---

class BreakableMachine(LoggingMachine):
    def __init__(self, env, id, logger, failure_shape=2.0, failure_scale=200.0,
                 repair_mean_log=2.0, repair_sigma_log=0.5, **kwargs):
        super().__init__(env, id, logger, **kwargs) # Pass logger to LoggingMachine
        self.failure_shape = failure_shape
        self.failure_scale = failure_scale
        self.repair_mean_log = repair_mean_log
        self.repair_sigma_log = repair_sigma_log

    def get_delay(self, delay):
        base = super().get_delay(delay)
        total, broke, down = compute_delay_with_breakdown(
            base, self.failure_shape, self.failure_scale,
            self.repair_mean_log, self.repair_sigma_log,
        )
        if broke:
            self.logger.log_downtime(self.env.now, self.id, down, "Weibull Breakdown")
        return total

class RouterMachine(LoggingMachine):
    def __init__(self, env, id, logger, defect_prob=0.05, max_attempts=2, **kwargs):
        kwargs["out_edge_selection"] = None
        super().__init__(env, id, logger, **kwargs)
        self.defect_prob = defect_prob
        self.max_attempts = max_attempts
        self.attempts = {}
        self._current_items = []
        self.out_edge_selection = self._route_out_edge

    def worker(self, item, processing_delay, req_token):
        # We must override worker to track the item BEFORE parent routing happens
        self._current_items.append(item)
        try:
            # Call the parent worker (which logs ENTRY/EXIT)
            yield from super().worker(item, processing_delay, req_token)
        finally:
            if item in self._current_items:
                self._current_items.remove(item)

    def _route_out_edge(self):
        if not self._current_items:
            return 0
        
        item = self._current_items[0]
        attempts = self.attempts.get(item.id, 0) + 1
        self.attempts[item.id] = attempts
        
        measurement = 5.0 + (0.3 if defect_roll(self.defect_prob) else 0.0)
        result = "PASS" if measurement <= 5.2 else "FAIL"
        
        self.logger.log_quality_inspection(self.env.now, item.id, self.id, measurement, 5.2, result)

        if result == "FAIL":
            if attempts >= self.max_attempts:
                self.logger.log_scrap(self.env.now, item.id, self.id, "Repeated failure")
                return 1
            else:
                self.logger.log_rework(self.env.now, item.id, self.id, attempts, "Voltage out of bounds")
                return 1
        
        return 0

    
# --- Simulation Run ---
def run_simulation(sim_time=1000):
    env = simpy.Environment()
    logger = EventLogger()

        # Nodes
    source = LoggingSource(env, id="SOURCE", logger=logger, inter_arrival_time=5.0)
    
    pcb_assembly = BreakableMachine(env, id="PCB_ASSEMBLY", logger=logger, processing_delay=lambda: cycle_time(0.7, 0.15))
    mech_assembly = BreakableMachine(env, id="MECH_ASSEMBLY", logger=logger, processing_delay=lambda: cycle_time(1.1, 0.2))
    
    elec_testing = RouterMachine(env, id="ELEC_TESTING", logger=logger, defect_prob=0.05, processing_delay=lambda: cycle_time(0.4, 0.1))
    
    rework = LoggingMachine(env, id="REWORK", logger=logger, processing_delay=lambda: cycle_time(1.3, 0.3))
    
    final_inspection = RouterMachine(env, id="FINAL_INSPECTION", logger=logger, defect_prob=0.02, max_attempts=1, processing_delay=lambda: cycle_time(0.7, 0.15))
    
    packaging = LoggingMachine(env, id="PACKAGING", logger=logger, processing_delay=lambda: cycle_time(0.0, 0.1))
    
    sink = Sink(env, id="SINK")
    scrap_sink = Sink(env, id="SCRAP")

    # Buffers
    buf_pcb = Buffer(env, id="BUF_PCB", capacity=10)
    buf_mech = Buffer(env, id="BUF_MECH", capacity=10)
    buf_test = Buffer(env, id="BUF_TEST", capacity=10)
    buf_inspect = Buffer(env, id="BUF_INSPECT", capacity=10)
    buf_rework = Buffer(env, id="BUF_REWORK", capacity=10)
    buf_test_in = Buffer(env, id="BUF_TEST_IN", capacity=10)
    buf_pack = Buffer(env, id="BUF_PACK", capacity=10)
    buf_scrap = Buffer(env, id="BUF_SCRAP", capacity=10)
    buf_sink = Buffer(env, id="BUF_SINK", capacity=100)

    # Wiring
    buf_pcb.connect(source, pcb_assembly)
    buf_mech.connect(pcb_assembly, mech_assembly)
    buf_test.connect(mech_assembly, elec_testing)
    buf_inspect.connect(elec_testing, final_inspection)
    buf_rework.connect(elec_testing, rework)
    buf_test_in.connect(rework, elec_testing)
    buf_pack.connect(final_inspection, packaging)
    buf_scrap.connect(final_inspection, scrap_sink)
    buf_sink.connect(packaging, sink)

    print(f"Starting simulation for {sim_time} minutes...")
    # Mute the massive FactorySimPy internal print spam
    with contextlib.redirect_stdout(io.StringIO()):
        env.run(until=sim_time)
    print("Simulation complete.")

    # Report
    print(f"\n--- Simulation Summary ---")
    print(f"Items Packaged  : {sink.stats['num_item_received']}")
    print(f"Items Scrapped  : {scrap_sink.stats['num_item_received']}")
    print(f"\n--- Events Generated ---")
    for event_type, count in logger.counts.items():
        print(f"{event_type:20s}: {count}")
    print(f"\nAll events written to: {logger.file_path}")

if __name__ == "__main__":
    run_simulation()