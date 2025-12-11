from src.pypdevs.DEVS import AtomicDEVS
from environment import *
import abc
import dataclasses

# ============================================================================
# IMPORTANT: PyPDEVS List Wrapping
# ============================================================================
# This version of PyPDEVS requires all outputs to be wrapped in lists.
# 
# When sending output:
#   return {self.out_port: [value]}  # Wrap in list
#
# When receiving input:
#   value = inputs[self.in_port]
#   if isinstance(value, list):      # Unwrap if needed
#       value = value[0]
# ============================================================================

# ============================================================================
# Router: Dispatches products to machines based on their recipe
# ============================================================================

@dataclasses.dataclass
class RouterState:
    """
    State of the Router.
    """
    # Queue statistics tracking
    last_time: float = 0.0  # Time of last state change
    total_queue_area: float = 0.0  # Cumulative sum of (queue_length × time_duration)
    
    def __init__(self, machine_names, machine_capacities):
        self.queue = []
        self.machine_remaining = dict(machine_capacities)
        self.machine_batch_type = {m: None for m in machine_names}
        
        # FIX: Store capacities in state so the reset logic works
        self.machine_capacities = machine_capacities

        self.dispatch_product = None
        self.dispatch_target = None
        self.remaining_time = float("inf")

        self.last_time = 0.0
        self.total_queue_area = 0.0
        self.current_time = 0.0


class AbstractRouter(AtomicDEVS):
    """
    Abstract base class for routers.
    """
    def __init__(self, name, machine_names, machine_capacities, routing_time_per_size=30.0):
        super().__init__(name)
        
        # Parameters
        self.machine_names = machine_names
        self.routing_time_per_size = routing_time_per_size
        self.machine_capacities = machine_capacities
        
        # Input ports
        self.in_product = self.addInPort("in_product")
        self.in_capacity = {}
        for m in self.machine_names:
            self.in_capacity[m] = self.addInPort(f"in_capacity_{m}")
        
        # Output ports
        self.out_machine = {}
        for m in self.machine_names:
            self.out_machine[m] = self.addOutPort(f"out_{m}")
        self.out_sink = self.addOutPort("out_sink")
        
        # State
        self.state = RouterState(machine_names, machine_capacities)
        
    def _nextDestination(self, product):
        if product.current_step < len(product.recipe):
            return product.recipe[product.current_step]
        return "SINK"

    def _eligibleForMachine(self, product, machine_id):
        # 1. Check if this is the correct machine for the step
        if self._nextDestination(product) != machine_id:
            return False

        # 2. Check Capacity
        if product.size > self.state.machine_remaining[machine_id]:
            return False

        # 3. Check Batch Type Consistency
        # If machine has a batch type assigned, product must match it
        bt = self.state.machine_batch_type[machine_id]
        if bt is not None and product.product_type != bt:
            return False

        return True

    def _scheduleDispatchIfPossible(self):
        # Only schedule one dispatch at a time
        if self.state.dispatch_product is not None:
            return

        # 1. Try to dispatch to machines
        for m in self.machine_names:
            # Filter queue for eligible products
            waiting = [p for p in self.state.queue if self._eligibleForMachine(p, m)]
            chosen = self._selectProduct(waiting)
            
            if chosen is not None:
                self.state.dispatch_product = chosen
                self.state.dispatch_target = m
                self.state.remaining_time = chosen.size * self.routing_time_per_size
                return

        # 2. Try to dispatch to sink (products that are done)
        waiting_sink = [p for p in self.state.queue if self._nextDestination(p) == "SINK"]
        chosen = self._selectProduct(waiting_sink)
        
        if chosen is not None:
            self.state.dispatch_product = chosen
            self.state.dispatch_target = "SINK"
            self.state.remaining_time = chosen.size * self.routing_time_per_size


    @abc.abstractmethod
    def _selectProduct(self, waiting_products):
        pass
    
    def extTransition(self, inputs):
        # Update simulation time
        self.state.current_time += self.elapsed

        # Update queue statistics (before queue length changes)
        self.state.total_queue_area += len(self.state.queue) * (self.state.current_time - self.state.last_time)
        self.state.last_time = self.state.current_time

        # 1. Handle capacity notifications
        for m, port in self.in_capacity.items():
            if port in inputs:
                cap_val = inputs[port]
                if isinstance(cap_val, list):
                    cap_val = cap_val[0]
                self.state.machine_remaining[m] = int(cap_val)

                # Reset batch type when machine becomes empty
                if hasattr(self.state, "machine_capacities"):
                    if self.state.machine_remaining[m] == self.state.machine_capacities[m]:
                        self.state.machine_batch_type[m] = None
                
                # === FIX FOR RACE CONDITION ===
                # If we are currently routing to this machine, check if it is still eligible.
                # If the machine started processing (capacity=0) while we were routing,
                # we must ABORT the dispatch to prevent the ValueError.
                if (self.state.dispatch_target == m and 
                    self.state.dispatch_product is not None):
                    
                    if not self._eligibleForMachine(self.state.dispatch_product, m):
                        # Abort the dispatch. The product remains in the queue.
                        self.state.dispatch_product = None
                        self.state.dispatch_target = None
                        self.state.remaining_time = float("inf")

        # 2. Handle product arrivals
        if self.in_product in inputs:
            prod = inputs[self.in_product]
            if isinstance(prod, list):
                for p in prod:
                    self.state.queue.append(p)
            else:
                self.state.queue.append(prod)

        # 3. Try to schedule a dispatch
        # (If we aborted above, this will try to find a new valid destination immediately)
        self._scheduleDispatchIfPossible()
        return self.state

    
    def timeAdvance(self):
        if self.state.dispatch_product is None:
            return float("inf")
        return self.state.remaining_time

    
    def outputFnc(self):
        p = self.state.dispatch_product
        t = self.state.dispatch_target
        if p is None or t is None:
            return {}

        if t == "SINK":
            return {self.out_sink: [p]}

        return {self.out_machine[t]: [p]}

    
    def intTransition(self):
        # Advance time
        self.state.current_time += self.timeAdvance()

        # Update statistics
        self.state.total_queue_area += len(self.state.queue) * (self.state.current_time - self.state.last_time)
        self.state.last_time = self.state.current_time

        p = self.state.dispatch_product
        t = self.state.dispatch_target

        if p is not None and t is not None:
            # Remove from queue
            if p in self.state.queue:
                self.state.queue.remove(p)

            # If sending to a machine, update local tracking
            if t != "SINK":
                if self.state.machine_batch_type[t] is None:
                    self.state.machine_batch_type[t] = p.product_type

                self.state.machine_remaining[t] = max(
                    0, self.state.machine_remaining[t] - p.size
                )

        # Clear dispatch info
        self.state.dispatch_product = None
        self.state.dispatch_target = None
        self.state.remaining_time = float("inf")

        # Schedule next
        self._scheduleDispatchIfPossible()
        return self.state

  
    def getAverageQueueLength(self, current_time):
        if current_time > 0:
            return self.state.total_queue_area / current_time
        return 0.0


class FIFORouter(AbstractRouter):
    """
    FIFO Router: Dispatches products in First-In-First-Out order.
    """
    def __init__(self, machine_names, machine_capacities, routing_time_per_size=30.0):
        super().__init__("FIFORouter", machine_names, machine_capacities, routing_time_per_size)
    
    def _selectProduct(self, waiting_products):
        if not waiting_products:
            return None
        # waiting_products preserves queue order, so index 0 is FIFO
        return waiting_products[0]


class PriorityRouter(AbstractRouter):
    """
    Priority Router: Dispatches larger products before smaller products.
    """
    def __init__(self, machine_names, machine_capacities, routing_time_per_size=30.0):
        super().__init__("PriorityRouter", machine_names, machine_capacities, routing_time_per_size)
    
    def _selectProduct(self, waiting_products):
        if not waiting_products:
            return None
        # Priority:
        # 1. Higher Step (further along) -> Descending
        # 2. Larger Size -> Descending
        # 3. Earlier Arrival -> Ascending (preserved by stable sort on queue order)
        
        # Since Python sort is stable, we just sort by step and size. 
        # The arrival order (FIFO) is broken only by these keys.
        return sorted(
            waiting_products,
            key=lambda p: (-p.current_step, -p.size)
        )[0]


# ============================================================================
# Machine: Processes products with batch capacity and max wait time
# ============================================================================

@dataclasses.dataclass
class MachineState:
    """
    State of a Machine.
    """
    # Statistics tracking
    total_processing_time: float = 0.0
    total_occupancy_product: float = 0.0
    num_batches: int = 0
    
    def __init__(self, capacity):
        self.current_time = 0.0
        self.capacity = capacity
        
        self.products = []
        self.batch_type = None
        
        self.mode = "IDLE" # IDLE, WAITING, PROCESSING
        self.first_entry_time = None
        self.remaining_time = float("inf")
        self.next_event = None # START, FINISH
    
    def usedCapacity(self):
        return sum(p.size for p in self.products)


class Machine(AtomicDEVS):
    """
    Machine processes products in batches.
    """
    def __init__(self, machine_id, capacity, max_wait_duration):
        super().__init__(f"Machine_{machine_id}")
        
        self.machine_id = machine_id
        self.capacity = capacity
        self.max_wait_duration = max_wait_duration
        
        self.state = MachineState(capacity)
        
        self.in_product = self.addInPort("in_product")
        self.out_product = self.addOutPort("out_product")
        self.out_capacity = self.addOutPort("out_capacity")

    
    def extTransition(self, inputs):
        # Update internal timer
        if self.state.mode != "IDLE":
             self.state.remaining_time = max(0.0, self.state.remaining_time - self.elapsed)
        
        self.state.current_time += self.elapsed

        if self.in_product in inputs:
            products_in = inputs[self.in_product]
            if not isinstance(products_in, list):
                products_in = [products_in]

            for p in products_in:
                if self.state.mode == "PROCESSING":
                    raise ValueError(f"Machine {self.machine_id} received product while PROCESSING. Router bug.")

                # Set batch type if empty
                if not self.state.products:
                    self.state.batch_type = p.product_type
                elif p.product_type != self.state.batch_type:
                    raise ValueError(f"Machine {self.machine_id} mixed types {self.state.batch_type} vs {p.product_type}. Router bug.")

                self.state.products.append(p)
                
                # Start waiting timer if this is the first product
                if self.state.mode == "IDLE":
                    self.state.mode = "WAITING"
                    self.state.first_entry_time = self.state.current_time

        # Determine if we should start processing
        used = self.state.usedCapacity()

        # 1. Full capacity -> Start immediately
        if used >= self.capacity:
            self.state.mode = "WAITING" # Transitional
            self.state.remaining_time = 0.0
            self.state.next_event = "START"
            return self.state

        # 2. Wait duration logic
        if self.state.products:
            # We are waiting. Recalculate remaining wait time.
            elapsed_wait = self.state.current_time - self.state.first_entry_time
            wait_left = max(0.0, self.max_wait_duration - elapsed_wait)
            
            self.state.mode = "WAITING"
            self.state.remaining_time = wait_left
            self.state.next_event = "START"
        
        return self.state

    
    def timeAdvance(self):
        if self.state.mode == "IDLE":
            return float("inf")
        return self.state.remaining_time
    
    def outputFnc(self):
        if self.state.next_event == "START":
            # Notify Router that effective capacity is now 0 (machine is busy)
            return {self.out_capacity: [0]}
            
        if self.state.next_event == "FINISH":
            # Output processed products and notify full capacity restored
            return {
                self.out_product: list(self.state.products),
                self.out_capacity: [self.capacity]
            }
        
        return {}
    
    def intTransition(self):
        self.state.current_time += self.timeAdvance()
        
        if self.state.next_event == "START":
            # Switch to PROCESSING
            if not self.state.products:
                # Should not happen if logic is correct, but safe fallback
                self.state.mode = "IDLE"
                self.state.remaining_time = float("inf")
                self.state.next_event = None
                return self.state

            # Processing time depends on product type
            p_sample = self.state.products[0]
            proc_time = p_sample.processing_times[self.machine_id]
            
            # Statistics
            used = self.state.usedCapacity()
            self.state.total_processing_time += proc_time
            self.state.total_occupancy_product += used * proc_time
            self.state.num_batches += 1
            
            self.state.mode = "PROCESSING"
            self.state.remaining_time = proc_time
            self.state.next_event = "FINISH"
            
        elif self.state.next_event == "FINISH":
            # Advance step for all products
            for p in self.state.products:
                p.current_step += 1
            
            # Reset machine
            self.state.products = []
            self.state.batch_type = None
            self.state.first_entry_time = None
            self.state.mode = "IDLE"
            self.state.remaining_time = float("inf")
            self.state.next_event = None
            
        return self.state

    
    def getStatistics(self, simulation_time):
        if simulation_time > 0:
            utilization = self.state.total_processing_time / simulation_time
        else:
            utilization = 0.0
        
        if self.state.total_processing_time > 0:
            avg_occupancy = self.state.total_occupancy_product / self.state.total_processing_time
        else:
            avg_occupancy = 0.0
        
        return (utilization, avg_occupancy, self.state.num_batches)