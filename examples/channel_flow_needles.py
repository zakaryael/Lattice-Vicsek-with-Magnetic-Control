from lvmc.core.simulation import Simulation
from lvmc.data_handling.data_collector import DataCollector
from lvmc.data_handling.data_exporter import DataExporter
from tqdm import tqdm
from utils import *
from rich import print
import numpy as np

# Parameters for ParticleLattice

width = 50
height = 25
g = 0.2
v0 = 100.0
density = 0.3
flow_params = {"type": "poiseuille", "v1": 0.0}
tmax = 1000
t0 = 0
    
def main():
    if flow_params["v1"] == 0:
        dt_flow = 2*tmax
        base_name = "noflow_"+str(width)+"_"+str(height)+"_"+str(g)+"_"+str(v0).removesuffix('.0')
    else: 
        dt_flow = 0.1/flow_params["v1"]
        base_name = flow_params["type"]+"_"+str(width)+"_"+str(height)+"_"+str(g)+"_"+str(v0).removesuffix('.0')+"_"+str(flow_params["v1"]).removesuffix('.0')
    fname_stats = "stat_"+base_name+".txt"
    dt_stat = 0.1
    dt_dump_stat = 5
    dt_dump_field = 50
    
    # Initialize the Simulation (test if restart of not)
    if t0==0:
        print("Starting simulation from scratch")
        simulation = Simulation(g, v0, width=width, height=height, density=density, flow_params=flow_params, with_transport=False)
        obstacles = torch.zeros((height, width), dtype=torch.bool)
        obstacles[0, :] = True
        obstacles[-1, :] = True
        simulation.lattice.set_obstacles(obstacles)
    else:
        fname =  "fields_"+base_name+"_"+("%1.2f"%(t0-dt_dump_field))+"_"+("%1.2f"%t0)+".h5"
        simulation = Simulation.init_from_file(fname)
    data_collector = DataCollector(simulation)
    
    tlast_flow = 0
    count_flow = 1
    count_stat = 1
    count_dump_stat = 1
    count_dump_field = 1
    simulation.init_stat()
    cnt = 0
    
    while simulation.t < tmax:
        event = simulation.run()
        
        if simulation.t-count_flow*dt_flow > dt_flow:
            dt_act = simulation.t-tlast_flow
            tlast_flow = np.copy(simulation.t)
            count_flow += 1
            Nshift = np.random.poisson(simulation.flow.velocity_field[0,1:-1,0]*dt_act)
            for iy in range(1,simulation.lattice.height-1):
                if Nshift[iy-1]>0:
                    cnt += Nshift[iy-1]
                    X = np.argwhere(simulation.lattice.occupancy_map[iy,:]).squeeze().tolist()
                    O = simulation.lattice.orientation_map[iy,X]
                    for x in X:
                        simulation.lattice.remove_particle(x,iy)
                    for ix in range(len(X)):
                        simulation.add_particle((X[ix]+Nshift[iy-1])%simulation.lattice.width, iy, O[ix])
                    simulation.stat_flux_counter[iy] += Nshift[iy-1]*len(X)
            simulation.initialize_rates()
        
        if simulation.t-count_stat*dt_stat > dt_stat:
            count_stat += 1
            simulation.perform_stat()
            print(simulation.lattice.visualize_lattice())
            print("t = %f, Performed %d shifts" % (simulation.t,cnt))
            cnt = 0
            data_collector.collect_snapshot()
            
        if simulation.t-count_dump_stat*dt_dump_stat > dt_dump_stat:
            count_dump_stat += 1
            simulation.dump_stat(fname_stats)
            
        if simulation.t-count_dump_field*dt_dump_field > dt_dump_field:
            fname_dumps = "fields_"+base_name+"_"+("%1.2f"%tlast_dump_field)+"_"+("%1.2f"%simulation.t)+".h5"
            count_dump_field += 1
            data_exporter = DataExporter(fname_dumps, data_collector)
            data_exporter.export_data()
            data_collector = DataCollector(simulation)
    
    print(simulation.lattice.visualize_lattice())
    print("t = %f, Performed %d shifts" % (simulation.t,cnt))
    data_collector.collect_snapshot()
    simulation.dump_stat(fname_stats)
    fname_dumps = "fields_"+base_name+"_"+("%1.2f"%tlast_dump_field)+"_"+("%1.2f"%simulation.t)+".h5"
    data_exporter = DataExporter(fname_dumps, data_collector)
    data_exporter.export_data()
            
if __name__ == "__main__":
    main()
