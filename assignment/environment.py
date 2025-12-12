import random
from src.pypdevs.DEVS import AtomicDEVS

class Product:
    def __init__(self, product_type, size, recipe, processing_times, arrival_time):
        self.product_type = product_type
        self.size = size
        self.recipe = recipe
        self.processing_times = processing_times
        self.arrival_time = arrival_time
        
        self.current_step = 0
        self.flow_time = 0.0
        
        # --- NEW Fields for Spoilage Task ---
        self.router_entry_time = 0.0
        self.is_spoiled = False

    def __repr__(self):
        return (f"Product(type={self.product_type}, size={self.size}, "
                f"step={self.current_step}, spoiled={self.is_spoiled})")

class GeneratorState:
    def __init__(self):
        self.next_time = 0.0

class Generator(AtomicDEVS):
    def __init__(self, seed, lambd, gen_types):
        super().__init__("Generator")
        self.rng = random.Random(seed)
        self.lambd = lambd
        self.gen_types = gen_types
        self.state = GeneratorState()
        self.out_product = self.addOutPort("out_product")
        
    def timeAdvance(self):
        return self.state.next_time

    def intTransition(self):
        # Uniform distribution (0, 2/lambda) to match average rate
        self.state.next_time = self.rng.uniform(0, 2.0 / self.lambd)
        return self.state
        
    def outputFnc(self):
        r = self.rng.random()
        cum_prob = 0
        selected = self.gen_types[-1]
        for gt in self.gen_types:
            cum_prob += gt[4]
            if r <= cum_prob:
                selected = gt
                break
        
        # Note: In a real simulation, we'd accumulate time. 
        # Here we rely on the system passing products.
        p = Product(
            product_type=selected[0],
            size=selected[1],
            recipe=selected[2],
            processing_times=selected[3],
            arrival_time=0.0 # Placeholder, arrival tracked by flow logic if needed
        )
        return {self.out_product: [p]}

class SinkState:
    def __init__(self):
        self.products = []
        self.current_time = 0.0

class Sink(AtomicDEVS):
    def __init__(self, target_num):
        super().__init__("Sink")
        self.target_num = target_num
        self.in_product = self.addInPort("in_product")
        self.state = SinkState()
        
    def extTransition(self, inputs):
        self.state.current_time += self.elapsed
        
        if self.in_product in inputs:
            prods = inputs[self.in_product]
            if not isinstance(prods, list): prods = [prods]
            for p in prods:
                # We calculate flow time relative to the system clock 
                # (Assuming p.arrival_time was set correctly by Generator or Router wrapper. 
                # If not, we just use current_time as exit time for analysis).
                p.flow_time = self.state.current_time - p.arrival_time
                self.state.products.append(p)
        return self.state
        
    def termination_condition(self):
        # Only count non-spoiled products for the target
        non_spoiled = [p for p in self.state.products if not p.is_spoiled]
        return len(non_spoiled) >= self.target_num