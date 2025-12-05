from src.pypdevs.DEVS import AtomicDEVS
from environment import *
import abc
import dataclasses
import math

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
#
# This applies to:
# - Products sent between components
# - Capacity notifications (integers) sent from Machines to Router
# ============================================================================

# ============================================================================
# Router: Dispatches products to machines based on their recipe
# ============================================================================

@dataclasses.dataclass
class RouterState:
    # Queue statistics tracking
    last_time: float = 0.0
    total_queue_area: float = 0.0

    def __init__(self, machine_names, machine_capacities):
        self.current_time = 0.0

        self.machine_names = list(machine_names)
        self.machine_capacities = dict(machine_capacities)

        # Products waiting to be dispatched
        self.queue: list[Product] = []

        # Remaining capacity per machine (size-based)
        self.machine_remaining = {
            m: self.machine_capacities[m] for m in self.machine_names
        }

        # Current batch type being built in each machine (None if empty)
        self.machine_batch_type = {m: None for m in self.machine_names}

        # Dispatch bookkeeping
        self.dispatch_product: Product | None = None
        self.dispatch_target: str | None = None  # machine_id or "SINK"
        self.routing_remaining: float = math.inf

        # Stats
        self.last_time = 0.0
        self.total_queue_area = 0.0

    def update_queue_area(self, now):
        # Update area using queue length before any change
        self.total_queue_area += len(self.queue) * (now - self.last_time)
        self.last_time = now

class AbstractRouter(AtomicDEVS):
    """
    Abstract base class for routers.
    
    The router takes time to dispatch products, with larger products taking longer.
    Routing time = product.size × routing_time_per_size
    
    The Router receives products from:
    - Generator (new products entering the system)
    - Machines (products that have completed an operation)
    
    The Router sends products to:
    - Machines (for their next operation)
    - Sink (if all operations are complete)
    
    You need to define appropriate input/output ports and implement the DEVS functions.
    """
    def __init__(self, name, machine_names, machine_capacities, routing_time_per_size=30.0):
        super().__init__(name)

        self.machine_names = machine_names
        self.machine_capacities = machine_capacities
        self.routing_time_per_size = routing_time_per_size

        # Input ports
        self.in_product = self.addInPort("in_product")  # from generator + machines (we'll connect multiple)
        self.in_capacity = {
            m: self.addInPort(f"in_capacity_{m}") for m in self.machine_names
        }

        # Output ports
        self.out_machine = {
            m: self.addOutPort(f"out_{m}") for m in self.machine_names
        }
        self.out_sink = self.addOutPort("out_sink")

        self.state = RouterState(machine_names, machine_capacities)
    
    @abc.abstractmethod
    def _selectProduct(self, waiting_products):
        """
        Select which product to dispatch next from a list of waiting products.
        This method should be implemented by subclasses (FIFORouter, PriorityRouter).
        
        Args:
            waiting_products: List of products waiting for the same machine
        
        Returns:
            The selected product, or None if list is empty
        """
        pass
    
    def _next_destination(self, product: Product):
        if product.current_step < len(product.recipe):
            return product.recipe[product.current_step]
        return "SINK"

    def _eligible_for_machine(self, product: Product, machine_id: str):
        # Must need this machine next
        if self._next_destination(product) != machine_id:
            return False

        # Must fit remaining capacity
        if product.size > self.state.machine_remaining[machine_id]:
            return False

        # Must match batch type if machine already has one
        bt = self.state.machine_batch_type[machine_id]
        if bt is not None and product.product_type != bt:
            return False

        return True

    def _try_schedule_dispatch(self):
        if self.state.dispatch_product is not None:
            return

        # 1) Prefer dispatchable products to machines in machine order
        for m in self.machine_names:
            if self.state.machine_remaining[m] <= 0:
                continue

            waiting = [p for p in self.state.queue if self._eligible_for_machine(p, m)]
            chosen = self._selectProduct(waiting)
            if chosen is not None:
                self.state.dispatch_product = chosen
                self.state.dispatch_target = m
                self.state.routing_remaining = chosen.size * self.routing_time_per_size
                return

        # 2) If no machine dispatch possible, consider finished products to sink
        waiting_sink = [p for p in self.state.queue if self._next_destination(p) == "SINK"]
        if waiting_sink:
            chosen = self._selectProduct(waiting_sink)
            if chosen is not None:
                self.state.dispatch_product = chosen
                self.state.dispatch_target = "SINK"
                self.state.routing_remaining = chosen.size * self.routing_time_per_size

    def extTransition(self, inputs):
        # TODO: Implement external transition
        # - Handle products arriving from generator or machines
        # - Update machine availability information if machines notify you
        # - Update queue statistics when queue length changes
        # - Decide if you can dispatch a product
        # Advance time
        now = self.state.current_time + self.elapsed
        self.state.update_queue_area(now)
        self.state.current_time = now

        # Handle capacity notifications
        for m, port in self.in_capacity.items():
            if port in inputs:
                cap_val = inputs[port]
                if isinstance(cap_val, list):
                    cap_val = cap_val[0]

                self.state.machine_remaining[m] = int(cap_val)

                # If machine reports full capacity, it's empty again -> reset batch type
                if self.state.machine_remaining[m] == self.machine_capacities[m]:
                    self.state.machine_batch_type[m] = None

        # Handle product arrivals (from generator OR machines)
        if self.in_product in inputs:
            prod = inputs[self.in_product]
            if isinstance(prod, list):
                prod = prod[0]
            self.state.queue.append(prod)

        # Try to schedule a dispatch
        self._try_schedule_dispatch()
        return self.state
    
    def timeAdvance(self):
        # TODO: Return routing time (product.size × routing_time_per_size) if dispatching,
        # otherwise return inf when idle
        if self.state.dispatch_product is None:
            return math.inf
        return self.state.routing_remaining
    
    def outputFnc(self):
        # TODO: Output product to appropriate machine or sink
        p = self.state.dispatch_product
        t = self.state.dispatch_target
        if p is None or t is None:
            return {}

        if t == "SINK":
            return {self.out_sink: [p]}

        return {self.out_machine[t]: [p]}
    
    def intTransition(self):
        # TODO: Update state after dispatching a product
        # - Update queue statistics when queue length changes
        # Advance time
        now = self.state.current_time + self.timeAdvance()
        self.state.update_queue_area(now)
        self.state.current_time = now

        p = self.state.dispatch_product
        t = self.state.dispatch_target

        if p is not None and t is not None:
            # Remove from queue
            try:
                self.state.queue.remove(p)
            except ValueError:
                pass

            # Update machine bookkeeping if going to a machine
            if t != "SINK":
                # If starting a new batch, set batch type
                if self.state.machine_batch_type[t] is None:
                    self.state.machine_batch_type[t] = p.product_type

                # Decrease remaining capacity
                self.state.machine_remaining[t] = max(
                    0, self.state.machine_remaining[t] - p.size
                )

        # Clear dispatch state
        self.state.dispatch_product = None
        self.state.dispatch_target = None
        self.state.routing_remaining = math.inf

        # Schedule next if possible
        self._try_schedule_dispatch()
        return self.state
    
    def getAverageQueueLength(self, current_time):
        """
        Calculate the time-weighted average queue length.
        
        Args:
            current_time: The current simulation time
        
        Returns:
            The average queue length over the simulation period
        
        Note: You must update self.state.total_queue_area and self.state.last_time 
              in both extTransition and intTransition whenever the queue length changes.
              Formula: total_queue_area += queue_length * (current_time - last_time)
        """
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
        # FIFO by arrival_time then stable order
        return min(waiting_products, key=lambda p: p.arrival_time)


class PriorityRouter(AbstractRouter):
    """
    Priority Router: Dispatches larger products before smaller products.
    """
    def __init__(self, machine_names, machine_capacities, routing_time_per_size=30.0):
        super().__init__("PriorityRouter", machine_names, machine_capacities, routing_time_per_size)

    def _selectProduct(self, waiting_products):
        if not waiting_products:
            return None
        # Match the assignment priority order:
        # 1) Higher current_step
        # 2) Larger size
        # 3) Earlier arrival
        return sorted(
            waiting_products,
            key=lambda p: (-p.current_step, -p.size, p.arrival_time)
        )[0]


# ============================================================================
# Machine: Processes products with batch capacity and max wait time
# ============================================================================

@dataclasses.dataclass
class MachineState:
    """
    State of a Machine.
    
    You will need to track:
    - Products currently in the machine
    - Current mode (e.g., waiting, processing, notifying)
    - Remaining time until processing starts/completes
    """
    # Statistics tracking
    total_processing_time: float = 0.0  # Total time spent processing
    total_occupancy_product: float = 0.0  # Sum of (capacity_used * processing_duration)
    num_batches: int = 0  # Number of batches processed
    
    def __init__(self, capacity):
        # TODO: Initialize your machine state
        # Note: Statistics are already initialized above
        self.current_time = 0.0

        self.capacity = capacity
        self.products: list[Product] = []
        self.batch_type: int | None = None

        # Modes: IDLE, WAITING, PROCESSING
        self.mode = "IDLE"

        # Timing
        self.first_entry_time: float | None = None
        self.remaining: float = math.inf
        self.next_event: str | None = None  # "START" or "FINISH"

        # Stats already initialized above
        self.total_processing_time = 0.0
        self.total_occupancy_product = 0.0
        self.num_batches = 0
    
    def usedCapacity(self):
        """Calculate how much capacity is currently used."""
        # TODO: Sum up sizes of products in the machine
        return sum(p.size for p in self.products)


class Machine(AtomicDEVS):
    """
    Machine processes products in batches.
    
    Parameters:
        machine_id (str): Identifier for this machine (e.g., 'A', 'B')
        capacity (int): Maximum capacity of the machine
        max_wait_duration (float): Maximum time to wait before processing a non-full batch
    
    Behavior:
    - Accepts products from router (if capacity allows)
    - IMPORTANT: Can only batch products of the SAME product_type together
      * When receiving a product, validate it matches the existing batch type (if any)
      * Raise ValueError if different types are mixed (this catches Router bugs)
    - Waits for more products or until max_wait_duration expires
    - Processing duration comes from product.processing_times[machine_id]
      * All products in a batch have same type, so same processing time
    - Processes all products in batch
    - Sends processed products back to router
    
    You need to define appropriate input/output ports and implement the DEVS functions.
    """
    def __init__(self, machine_id, capacity, max_wait_duration):
        super().__init__(f"Machine_{machine_id}")

        self.machine_id = machine_id
        self.capacity = capacity
        self.max_wait_duration = max_wait_duration

        self.state = MachineState(capacity)

        # Input port
        self.in_product = self.addInPort("in_product")

        # Output ports
        self.out_product = self.addOutPort("out_product")   # back to router
        self.out_capacity = self.addOutPort("out_capacity") # notify router (int)
    
    def _schedule_waiting(self):
        # Compute time until start based on max_wait_duration
        assert self.state.mode == "WAITING"
        now = self.state.current_time

        used = self.state.usedCapacity()
        if used >= self.capacity:
            self.state.remaining = 0.0
        else:
            waited = now - (self.state.first_entry_time or now)
            self.state.remaining = max(0.0, self.max_wait_duration - waited)

        self.state.next_event = "START"

    def _start_processing(self):
        # All products in batch have same type -> same processing time
        if not self.state.products:
            # Should not happen
            self.state.mode = "IDLE"
            self.state.remaining = math.inf
            self.state.next_event = None
            return

        proc_time = self.state.products[0].processing_times[self.machine_id]

        # Update stats required by spec
        used = self.state.usedCapacity()
        self.state.total_processing_time += proc_time
        self.state.total_occupancy_product += used * proc_time
        self.state.num_batches += 1

        self.state.mode = "PROCESSING"
        self.state.remaining = proc_time
        self.state.next_event = "FINISH"
    
    def extTransition(self, inputs):
        # TODO: Implement external transition
        # - Handle incoming products from router
        # - Update remaining time if already waiting
        # - Decide when to start processing
        # Advance time
        self.state.current_time += self.elapsed

        # Get incoming product
        if self.in_product not in inputs:
            return self.state

        prod = inputs[self.in_product]
        if isinstance(prod, list):
            prod = prod[0]

        # If already processing, router bug
        if self.state.mode == "PROCESSING":
            raise ValueError(
                f"Machine {self.machine_id} received product while processing. Router bug."
            )

        # Validate batch type consistency
        if self.state.batch_type is None:
            self.state.batch_type = prod.product_type
        elif prod.product_type != self.state.batch_type:
            raise ValueError(
                f"Machine {self.machine_id} mixed product types "
                f"{self.state.batch_type} and {prod.product_type}. Router bug."
            )

        # Add product
        self.state.products.append(prod)

        # If this is the first product
        if self.state.mode == "IDLE":
            self.state.mode = "WAITING"
            self.state.first_entry_time = self.state.current_time

        # Reschedule waiting timer
        self._schedule_waiting()
        return self.state
    
    def timeAdvance(self):
        # TODO: Return appropriate time based on current mode
        if self.state.mode == "IDLE":
            return math.inf
        return self.state.remaining
    
    def outputFnc(self):
        # TODO: Output processed products or availability notifications
         # START event: notify router that machine is not available anymore
        if self.state.next_event == "START":
            return {self.out_capacity: [0]}

        # FINISH event: send all products back + notify full capacity
        if self.state.next_event == "FINISH":
            out = {}
            # Products back to router
            if self.state.products:
                out[self.out_product] = list(self.state.products)  # already a list of products
            # Capacity reset notification
            out[self.out_capacity] = [self.capacity]
            return out

        return {}
    
    def intTransition(self):
        # TODO: Update state after processing or notifying. Also update statistics.
        # Advance time
        self.state.current_time += self.timeAdvance()

        if self.state.next_event == "START":
            # Transition to PROCESSING
            self._start_processing()
            return self.state

        if self.state.next_event == "FINISH":
            # Update products step and clear batch
            for p in self.state.products:
                p.current_step += 1

            self.state.products.clear()
            self.state.batch_type = None
            self.state.first_entry_time = None

            self.state.mode = "IDLE"
            self.state.remaining = math.inf
            self.state.next_event = None
            return self.state

        return self.state
    
    def getStatistics(self, simulation_time):
        """
        Get machine utilization statistics (pre-implemented for performance analysis).
        Returns: (utilization, avg_occupancy, num_batches)
        """
        if simulation_time > 0:
            utilization = self.state.total_processing_time / simulation_time
        else:
            utilization = 0.0
        
        if self.state.total_processing_time > 0:
            avg_occupancy = self.state.total_occupancy_product / self.state.total_processing_time
        else:
            avg_occupancy = 0.0
        
        return (utilization, avg_occupancy, self.state.num_batches)

