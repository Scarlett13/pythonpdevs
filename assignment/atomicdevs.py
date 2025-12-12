from src.pypdevs.DEVS import AtomicDEVS
from environment import *
import abc
import dataclasses

@dataclasses.dataclass
class RouterState:
    last_time: float = 0.0
    total_queue_area: float = 0.0
    
    def __init__(self, machine_names, machine_capacities):
        self.queue = []
        self.machine_remaining = dict(machine_capacities)
        self.machine_batch_type = {m: None for m in machine_names}
        self.machine_capacities = machine_capacities

        self.dispatch_product = None
        self.dispatch_target = None
        self.remaining_time = float("inf")

        self.last_time = 0.0
        self.total_queue_area = 0.0
        self.current_time = 0.0

class AbstractRouter(AtomicDEVS):
    def __init__(self, name, machine_names, machine_capacities, routing_time_per_size=30.0):
        super().__init__(name)
        self.machine_names = machine_names
        self.routing_time_per_size = routing_time_per_size
        self.machine_capacities = machine_capacities
        
        self.in_product = self.addInPort("in_product")
        self.in_capacity = {}
        for m in self.machine_names:
            self.in_capacity[m] = self.addInPort(f"in_capacity_{m}")
        
        self.out_machine = {}
        for m in self.machine_names:
            self.out_machine[m] = self.addOutPort(f"out_{m}")
        self.out_sink = self.addOutPort("out_sink")
        
        self.state = RouterState(machine_names, machine_capacities)
        
    def _nextDestination(self, product):
        # Spoilage Override: If spoiled, go to SINK immediately
        if product.is_spoiled:
            return "SINK"
            
        if product.current_step < len(product.recipe):
            return product.recipe[product.current_step]
        return "SINK"

    def _eligibleForMachine(self, product, machine_id):
        if self._nextDestination(product) != machine_id: return False
        if product.size > self.state.machine_remaining[machine_id]: return False
        bt = self.state.machine_batch_type[machine_id]
        if bt is not None and product.product_type != bt: return False
        return True

    def _checkSpoilage(self, product):
        """Check if WIP product has spoiled."""
        if product.current_step == 0: return False # Fresh products don't spoil
        if product.is_spoiled: return True # Already marked
        
        last_machine = product.recipe[product.current_step - 1]
        threshold = 20*60 if last_machine == 'A' else 15*60
        
        waited = self.state.current_time - product.router_entry_time
        return waited > threshold

    def _scheduleDispatchIfPossible(self):
        if self.state.dispatch_product is not None:
            return

        # 1. Spoilage Check Pass
        # Identify spoiled items and force them to Sink
        for p in self.state.queue:
            if self._checkSpoilage(p):
                p.is_spoiled = True
                self.state.dispatch_product = p
                self.state.dispatch_target = "SINK"
                # Short routing time for disposal? Or standard? Using standard.
                self.state.remaining_time = p.size * self.routing_time_per_size
                return

        # 2. Try to dispatch to machines
        for m in self.machine_names:
            waiting = [p for p in self.state.queue if self._eligibleForMachine(p, m)]
            chosen = self._selectProduct(waiting)
            if chosen is not None:
                self.state.dispatch_product = chosen
                self.state.dispatch_target = m
                self.state.remaining_time = chosen.size * self.routing_time_per_size
                return

        # 3. Try to dispatch to sink (finished products)
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
        self.state.current_time += self.elapsed
        self.state.total_queue_area += len(self.state.queue) * (self.state.current_time - self.state.last_time)
        self.state.last_time = self.state.current_time

        # Handle Capacity
        for m, port in self.in_capacity.items():
            if port in inputs:
                cap_val = inputs[port]
                if isinstance(cap_val, list): cap_val = cap_val[0]
                self.state.machine_remaining[m] = int(cap_val)

                if hasattr(self.state, "machine_capacities"):
                    if self.state.machine_remaining[m] == self.state.machine_capacities[m]:
                        self.state.machine_batch_type[m] = None
                
                # Race condition fix
                if (self.state.dispatch_target == m and 
                    self.state.dispatch_product is not None):
                    if not self._eligibleForMachine(self.state.dispatch_product, m):
                        self.state.dispatch_product = None
                        self.state.dispatch_target = None
                        self.state.remaining_time = float("inf")

        # Handle Products
        if self.in_product in inputs:
            prod = inputs[self.in_product]
            if isinstance(prod, list):
                products = prod
            else:
                products = [prod]
            
            for p in products:
                # Mark entry time for spoilage tracking
                # NOTE: If coming from generator, arrival_time needs setting.
                # If coming from machine, it's WIP.
                p.router_entry_time = self.state.current_time
                if p.current_step == 0:
                    p.arrival_time = self.state.current_time # Fix for flow time calc
                    
                self.state.queue.append(p)

        self._scheduleDispatchIfPossible()
        return self.state

    def timeAdvance(self):
        if self.state.dispatch_product is None: return float("inf")
        return self.state.remaining_time
    
    def outputFnc(self):
        p = self.state.dispatch_product
        t = self.state.dispatch_target
        if p is None or t is None: return {}
        if t == "SINK": return {self.out_sink: [p]}
        return {self.out_machine[t]: [p]}
    
    def intTransition(self):
        self.state.current_time += self.timeAdvance()
        self.state.total_queue_area += len(self.state.queue) * (self.state.current_time - self.state.last_time)
        self.state.last_time = self.state.current_time

        p = self.state.dispatch_product
        t = self.state.dispatch_target

        if p is not None:
            if p in self.state.queue: self.state.queue.remove(p)
            
            if t != "SINK":
                if self.state.machine_batch_type[t] is None:
                    self.state.machine_batch_type[t] = p.product_type
                self.state.machine_remaining[t] = max(0, self.state.machine_remaining[t] - p.size)

        self.state.dispatch_product = None
        self.state.dispatch_target = None
        self.state.remaining_time = float("inf")
        self._scheduleDispatchIfPossible()
        return self.state
        
    def getAverageQueueLength(self, current_time):
        if current_time > 0: return self.state.total_queue_area / current_time
        return 0.0

class FIFORouter(AbstractRouter):
    def __init__(self, machine_names, machine_capacities, routing_time_per_size=30.0):
        super().__init__("FIFORouter", machine_names, machine_capacities, routing_time_per_size)
    def _selectProduct(self, waiting_products):
        if not waiting_products: return None
        return waiting_products[0]

class PriorityRouter(AbstractRouter):
    def __init__(self, machine_names, machine_capacities, routing_time_per_size=30.0):
        super().__init__("PriorityRouter", machine_names, machine_capacities, routing_time_per_size)
    def _selectProduct(self, waiting_products):
        if not waiting_products: return None
        return sorted(waiting_products, key=lambda p: (-p.current_step, -p.size))[0]

# Machine Class (Same as previous fix)
@dataclasses.dataclass
class MachineState:
    total_processing_time: float = 0.0
    total_occupancy_product: float = 0.0
    num_batches: int = 0
    def __init__(self, capacity):
        self.current_time = 0.0
        self.capacity = capacity
        self.products = []
        self.batch_type = None
        self.mode = "IDLE"
        self.first_entry_time = None
        self.remaining_time = float("inf")
        self.next_event = None
    def usedCapacity(self):
        return sum(p.size for p in self.products)

class Machine(AtomicDEVS):
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
        if self.state.mode != "IDLE":
             self.state.remaining_time = max(0.0, self.state.remaining_time - self.elapsed)
        self.state.current_time += self.elapsed

        if self.in_product in inputs:
            products_in = inputs[self.in_product]
            if not isinstance(products_in, list): products_in = [products_in]
            for p in products_in:
                if self.state.mode == "PROCESSING":
                    raise ValueError(f"Machine {self.machine_id} received product while PROCESSING.")
                if not self.state.products: self.state.batch_type = p.product_type
                elif p.product_type != self.state.batch_type:
                    raise ValueError(f"Machine {self.machine_id} mixed types.")
                self.state.products.append(p)
                if self.state.mode == "IDLE":
                    self.state.mode = "WAITING"
                    self.state.first_entry_time = self.state.current_time

        used = self.state.usedCapacity()
        if used >= self.capacity:
            self.state.mode = "WAITING"
            self.state.remaining_time = 0.0
            self.state.next_event = "START"
            return self.state

        if self.state.products:
            elapsed_wait = self.state.current_time - self.state.first_entry_time
            wait_left = max(0.0, self.max_wait_duration - elapsed_wait)
            self.state.mode = "WAITING"
            self.state.remaining_time = wait_left
            self.state.next_event = "START"
        return self.state

    def timeAdvance(self):
        if self.state.mode == "IDLE": return float("inf")
        return self.state.remaining_time
    
    def outputFnc(self):
        if self.state.next_event == "START": return {self.out_capacity: [0]}
        if self.state.next_event == "FINISH":
            return {self.out_product: list(self.state.products), self.out_capacity: [self.capacity]}
        return {}
    
    def intTransition(self):
        self.state.current_time += self.timeAdvance()
        if self.state.next_event == "START":
            if not self.state.products:
                self.state.mode = "IDLE"; self.state.remaining_time = float("inf"); self.state.next_event = None
                return self.state
            proc_time = self.state.products[0].processing_times[self.machine_id]
            used = self.state.usedCapacity()
            self.state.total_processing_time += proc_time
            self.state.total_occupancy_product += used * proc_time
            self.state.num_batches += 1
            self.state.mode = "PROCESSING"
            self.state.remaining_time = proc_time
            self.state.next_event = "FINISH"
        elif self.state.next_event == "FINISH":
            for p in self.state.products: p.current_step += 1
            self.state.products = []; self.state.batch_type = None; self.state.first_entry_time = None
            self.state.mode = "IDLE"; self.state.remaining_time = float("inf"); self.state.next_event = None
        return self.state

    def getStatistics(self, simulation_time):
        if simulation_time > 0: util = self.state.total_processing_time / simulation_time
        else: util = 0.0
        if self.state.total_processing_time > 0: avg_occ = self.state.total_occupancy_product / self.state.total_processing_time
        else: avg_occ = 0.0
        return (util, avg_occ, self.state.num_batches)