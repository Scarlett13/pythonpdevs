from src.pypdevs.DEVS import CoupledDEVS
from atomicdevs import *

STRATEGY_FIFO = 0
STRATEGY_PRIORITY = 1

class FlexibleJobShop(CoupledDEVS):
    """
    The complete flexible job shop system.
    
    Parameters:
        seed (int): Random seed for generator
        target_num (int): Number of finished products required to terminate simulation
        gen_rate (float): Product generation rate (products/second)
        gen_types (list of tuples): Product types as (product_type, size, recipe, processing_times, probability)
        machine_capacities (dict): Capacity for each machine, e.g., {'A': 3, 'B': 2}
        dispatching_strategy (int): STRATEGY_FIFO or STRATEGY_PRIORITY
        max_wait_duration (float): Maximum wait time for all machines
        routing_time_per_size (float): Time to route a product per unit size
    """
    def __init__(self,
        seed=0,
        target_num=500,
        gen_rate=1.0/60.0/4.0,
        gen_types=[(0, 1, ['A', 'B'], {'A': 15*60, 'B': 10*60}, 2/3), (1, 2, ['B', 'A'], {'A': 20*60, 'B': 13*60}, 1/3)],
        machine_capacities={'A': 3, 'B': 2},
        dispatching_strategy=STRATEGY_FIFO,
        max_wait_duration=60.0*3.0,
        routing_time_per_size=30.0
    ):
        super().__init__("FlexibleJobShop")
        
        super().__init__("FlexibleJobShop")

        machine_names = list(machine_capacities.keys())

        generator = self.addSubModel(Generator(
            seed=seed,
            lambd=gen_rate,
            gen_types=gen_types,
        ))

        if dispatching_strategy == STRATEGY_FIFO:
            router = self.addSubModel(FIFORouter(
                machine_names=machine_names,
                machine_capacities=machine_capacities,
                routing_time_per_size=routing_time_per_size,
            ))
        elif dispatching_strategy == STRATEGY_PRIORITY:
            router = self.addSubModel(PriorityRouter(
                machine_names=machine_names,
                machine_capacities=machine_capacities,
                routing_time_per_size=routing_time_per_size,
            ))
        else:
            raise ValueError("Unknown dispatching strategy")

        machines = {}
        for mid, cap in machine_capacities.items():
            machines[mid] = self.addSubModel(Machine(
                machine_id=mid,
                capacity=cap,
                max_wait_duration=max_wait_duration,
            ))

        sink = self.addSubModel(Sink(target_num=target_num))

        # Connections
        # Generator -> Router (shared in_product)
        self.connectPorts(generator.out_product, router.in_product)

        # Router <-> Machines
        for mid, m in machines.items():
            # Router sends to machine
            self.connectPorts(router.out_machine[mid], m.in_product)

            # Machine sends products back to router
            self.connectPorts(m.out_product, router.in_product)

            # Machine capacity notifications -> Router
            self.connectPorts(m.out_capacity, router.in_capacity[mid])

        # Router -> Sink
        self.connectPorts(router.out_sink, sink.in_product)

        # Store references
        self.generator = generator
        self.router = router
        self.sink = sink
        self.machines = machines

