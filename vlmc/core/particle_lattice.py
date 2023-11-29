import torch
import torch.nn.functional as F
import numpy as np
import warnings


class ParticleLattice:
    """
    Class for the particle lattice.
    """

    ORIENTATION_LAYERS = [
        "up",
        "left",
        "down",
        "right",
    ]  # Class level constants for layer names
    NUM_ORIENTATIONS = 4  # Class level constant, shared by all instances of the class. Number of possible orientations for a particle

    def __init__(
        self,
        width: int,
        height: int,
        density: float = 0.0,
        obstacles: torch.Tensor = None,
        sinks: torch.Tensor = None,
    ):
        """
        Initialize the particle lattice.
        :param width: Width of the lattice.
        :param height: Height of the lattice.
        :param density: Density of particles in the lattice.
        :param obstacles: A binary matrix indicating the obstacle cells.
        :param sinks: A binary matrix indicating the sink cells.
        """
        self.width = width
        self.height = height
        self.num_layers = self.NUM_ORIENTATIONS  # Starting with 4 orientation layers

        # Initialize the lattice as a 3D tensor with dimensions corresponding to
        # layers/orientations, width, and height.
        self.griglia = torch.zeros((self.num_layers, height, width), dtype=torch.bool)

        # Layer indices will map layer names to their indices
        self.layer_indices = {name: i for i, name in enumerate(self.ORIENTATION_LAYERS)}

        # Initialize obstacles and sinks as zero tensors
        if obstacles is None:
            self.add_layer(torch.zeros((height, width), dtype=torch.bool), "obstacles")
        else:
            self.add_layer(obstacles, "obstacles")

        if sinks is None:
            self.add_layer(torch.zeros((height, width), dtype=torch.bool), "sinks")
        else:
            self.add_layer(sinks, "sinks")

        # Reference to the particle, sinks and obstacles layers for easy access
        self.particles = self.griglia[: self.NUM_ORIENTATIONS]
        self.sinks = self.griglia[self.layer_indices["sinks"]]
        self.obstacles = self.griglia[self.layer_indices["obstacles"]]

        # Initialize the lattice with particles at a given density.
        self.initialize_lattice(density)

    def _create_index_to_symbol_mapping(self):
        orientation_symbols = {"up": "↑", "down": "↓", "left": "←", "right": "→"}
        return {
            self.layer_indices[name]: symbol
            for name, symbol in orientation_symbols.items()
        }

    def __str__(self):
        index_to_symbol = self._create_index_to_symbol_mapping()
        obstacle_symbol = "■"  # Symbol for obstacles
        sink_symbol = "▼"  # Symbol for sinks
        particle_in_sink_symbol = "✱"  # Symbol for particle in a sink
        lattice_str = ""

        for y in range(self.height):
            row_str = ""
            for x in range(self.width):
                if self.obstacles[y, x]:
                    row_str += obstacle_symbol
                elif self.sinks[y, x]:
                    if not self.is_empty(x, y):  # Check for particle in sink
                        row_str += particle_in_sink_symbol
                    else:
                        row_str += sink_symbol
                elif self.is_empty(x, y):
                    row_str += "·"  # Use a dot for empty cells
                else:
                    orientation_index = self.get_particle_orientation(x, y)
                    symbol = index_to_symbol[orientation_index]
                    row_str += symbol
                row_str += " "  # Add space between cells
            lattice_str += row_str + "\n"

        return lattice_str

    def add_layer(self, layer: torch.Tensor, layer_name: str):
        """
        Add a new layer to the lattice.
        :param layer: A binary matrix indicating the special cells for the new layer.
        :param layer_name: Name of the layer to be added.
        """
        if layer.shape != (self.height, self.width):
            raise ValueError("Layer shape must match the dimensions of the lattice.")

        # Add the new layer to the lattice
        self.griglia = torch.cat((self.griglia, layer.unsqueeze(0)), dim=0)
        # Map the new layer's name to its index
        if layer_name in self.layer_indices:
            warnings.warn(
                f"Layer {layer_name} already exists. It will be overwritten.",
                stacklevel=2,
            )
            self.num_layers -= 1

        self.layer_indices[layer_name] = self.num_layers
        # Increment the number of layers
        self.num_layers += 1

    def initialize_lattice(self, density):
        """
        Initialize the lattice with particles at a given density.

        :param density: Density of particles to be initialized.
        :type density: float
        """
        num_cells = self.width * self.height
        num_particles = int(density * num_cells)
                
        
        # Randomly place particles
        positions = np.random.choice(
            num_cells, num_particles, replace=False
        )  # Randomly select positions by drawing num_particles samples from num_cells without replacement
        orientations = np.random.randint(
            0, ParticleLattice.NUM_ORIENTATIONS, num_particles
        )

        for pos, ori in zip(positions, orientations):
            y, x = divmod(
                pos, self.width
            )  # Convert position to (x, y) coordinates. divmod returns quotient and remainder.
            if not self.is_obstacle(x, y):
                self.add_particle(x, y, ori)

    def set_obstacle(self, x: int, y: int):
        """
        Set an obstacle at the specified position in the lattice,
        provided the cell is empty and not already an obstacle or a sink.

        Parameters:
        x (int): The x-coordinate of the position.
        y (int): The y-coordinate of the position.

        Raises:
        ValueError: If the specified position is outside the lattice bounds or already occupied.
        """
        if 0 <= x < self.width and 0 <= y < self.height:
            if not self.is_empty(x, y) or self.is_sink(x, y):
                raise ValueError(
                    "Cannot place an obstacle on a non-empty cell or a cell with a sink."
                )
            if self.is_sink(x, y):
                warnings.warn(
                    "Placing an obstacle on a sink will remove the sink. Make sure that this is intended",
                    stacklevel=2,
                )
                self.sinks[y, x] = False
            if self.is_obstacle(x, y):
                warnings.warn(
                    "Trying to place an obstacle on a cell that is already an obstacle. Please make sure that this is intended.",
                    stacklevel=2,
                )
            self.obstacles[y, x] = True
        else:
            raise ValueError("Position is outside the lattice bounds.")

    def set_sink(self, x: int, y: int):
        """
        Set a sink at the specified position in the lattice,
        provided the cell is empty and not already an obstacle or a sink.

        Parameters:
        x (int): The x-coordinate of the position.
        y (int): The y-coordinate of the position.

        Raises:
        ValueError: If the specified position is outside the lattice bounds or already occupied.
        """
        if 0 <= x < self.width and 0 <= y < self.height:
            if not self.is_empty(x, y) or self.is_obstacle(x, y):
                raise ValueError(
                    "Cannot place a sink on a non-empty cell or a cell with an obstacle."
                )
            if self.is_sink(x, y):
                warnings.warn(
                    "Trying to place a sink on a cell that is already a sink. Please make sure that this is intended.",
                    stacklevel=2,
                )
            self.sinks[y, x] = True
        else:
            raise ValueError("Position is outside the lattice bounds.")

    def is_empty(self, x, y):
        """
        Check if a cell is empty.

        :param x: x-coordinate of the lattice.
        :type x: int
        :param y: y-coordinate of the lattice.
        :type y: int
        :return: True if the no particle is present at the cell, False otherwise.
        :rtype: bool
        """
        return not self.particles[:, y, x].any()

    def add_particle(self, x, y, orientation):
        """
        Add a particle with a specific orientation at (x, y).

        :param x: x-coordinate of the lattice.
        :type x: int
        :param y: y-coordinate of the lattice.
        :type y: int
        :param orientation: Orientation of the particle.
        :type orientation: int
        """
        if self.is_empty(x, y) and not self.is_obstacle(x, y):
            #print('adding particle at index x=%d y=%d' %(x,y))
            #self.griglia[orientation, y, x] = True
            self.particles[orientation, y, x] = True
            #print(self.griglia[orientation, y, x] == True)
            #print(self.particles[orientation, y, x] == True)
            #print(sum(self.particles[:]))
            #print('added particle at index x=%d y=%d' %(x,y))
        else:
            raise ValueError("Cannot add particle, cell is occupied or is an obstacle. x=%d, y=%d" %(x,y))

    def remove_particle(self, x, y):
        """
        Remove a particle from a specific node in the lattice.

        :param x: x-coordinate of the node.
        :type x: int
        :param y: y-coordinate of the node.
        :type y: int
        """
        if self.is_empty(x, y):
            warnings.warn(
                "Trying to remove a particle from an empty cell. Please make sure that this is intended.",
                stacklevel=2,
            )
        if self.is_obstacle(x, y):
            warnings.warn(
                "Trying to remove a particle from an obstacle. Please make sure that this is intended.",
                stacklevel=2,
            )
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            raise ValueError(
                "Cannot remove particle, cell is outside the lattice bounds."
            )
        self.particles[:, y, x] = False  # Remove particle from all orientations
        #self.griglia[:, y, x] = False  # Remove particle from all orientations
        #print('removed particle from index x=%d y=%d' %(x,y))

    def add_particle_flux(self, number_of_particles, region):
        """
        Add a number of particles randomly within a specified region.

        :param number_of_particles: Number of particles to add.
        :type number_of_particles: int
        :param region: The region where particles are to be added, defined as (x_min, x_max, y_min, y_max).
        :type region: tuple
        """
        x_min, x_max, y_min, y_max = region
        for _ in range(number_of_particles):
            # Ensure that we add the particle in an empty spot
            while True:
                x = np.random.randint(x_min, x_max)
                y = np.random.randint(y_min, y_max)
                orientation = np.random.randint(0, self.num_layers)
                if self.is_empty(x, y):
                    self.add_particle(x, y, orientation)
                    break

    def query_lattice_state(self):
        """
        Query the current state of the lattice.

        :return: The state of the lattice.
        :rtype: torch.Tensor
        """
        return self.griglia

    def compute_tm(self, v0):
        """
        Compute the migration transition rate tensor TM with periodic boundary conditions.
        """
        # Calculate empty cells (where no particle is present)
        empty_cellspart = self.particles.sum(dim=0)
        empty_cells = ~(empty_cellspart + self.obstacles).bool()
        #empty_cells = ~self.griglia[:(self.NUM_ORIENTATIONS+1)].sum(dim=0).bool()

        # Calculate potential moves in each direction
        # Up
        TM_up = self.particles[self.layer_indices["up"]] * empty_cells.roll(
            shifts=+1, dims=0
        )
        # Down
        TM_down = self.particles[self.layer_indices["down"]] * empty_cells.roll(
            shifts=-1, dims=0
        )
        # Left
        TM_left = self.particles[self.layer_indices["left"]] * empty_cells.roll(
            shifts=+1, dims=1
        )
        # Right
        TM_right = self.particles[self.layer_indices["right"]] * empty_cells.roll(
            shifts=-1, dims=1
        )

        # Combine all moves
        TM = TM_up + TM_down + TM_left + TM_right

        return TM * v0

    def compute_log_tr(self):
        """
        Compute the reorientation transition log rate tensor.

        :return: The reorientation transition log rate tensor.
        """

        # Common kernel for convolution
        kernel = (
            torch.tensor([[0, 1, 0], [1, 0, 1], [0, 1, 0]], dtype=torch.float32)
            .unsqueeze(0)
            .unsqueeze(0)
        )

        # Convolve each orientation layer of the lattice using layer indices
        TR_tensor = torch.zeros(
            (ParticleLattice.NUM_ORIENTATIONS, self.height, self.width),
            dtype=torch.float32,
        )
        for index in range(ParticleLattice.NUM_ORIENTATIONS):
                        
            tmp_tensor = torch.cat((torch.cat((self.particles[index,:,-1].unsqueeze(-1),
                                          self.particles[index]),dim=1),self.particles[index,:,0].unsqueeze(-1)),dim=1)

            tmp_tensor = torch.cat((tmp_tensor[-1,:].unsqueeze(0),torch.cat((tmp_tensor,tmp_tensor[0,:].unsqueeze(0)),dim=0)),dim=0)

            input_tensor = tmp_tensor.unsqueeze(0).unsqueeze(0).float()
            TR_tensor[index] = F.conv2d(input_tensor, kernel, padding=0)[0, 0]

        # Adjusting the TR tensor based on orientation vectors
        up_index, down_index = self.layer_indices["up"], self.layer_indices["down"]
        left_index, right_index = (
            self.layer_indices["left"],
            self.layer_indices["right"],
        )

        TR_tensor[up_index], TR_tensor[down_index] = (
            TR_tensor[up_index] - TR_tensor[down_index],
            TR_tensor[down_index] - TR_tensor[up_index],
        )
        TR_tensor[left_index], TR_tensor[right_index] = (
            TR_tensor[left_index] - TR_tensor[right_index],
            TR_tensor[right_index] - TR_tensor[left_index],
        )

        return TR_tensor

    def compute_tr(self, g):
        """
        Compute the reorientation transition rate tensor TR.

        :param g: Parameter controlling alignment sensitivity. Default is 1.0.
        :type g: float
        """
        # Calculate occupied cells (where at least one particle is present)
        occupied_cells = self.particles.sum(dim=0).bool()

        log_tr = self.compute_log_tr()
        tr = torch.exp(g * log_tr) * occupied_cells

        #return tr
        return (tr * (torch.ones_like(self.particles) ^ self.particles )) #MODIFIED

    def get_target_position(self, x: int, y: int, orientation: int) -> tuple:
        """
        Get the expected position of a particle at (x, y) with a given orientation.

        :param x: Current x-coordinate of the particle.
        :param y: Current y-coordinate of the particle.
        :param orientation: Current orientation of the particle which determines the direction of movement.
        :return: The expected position of the particle.
        :rtype: tuple
        """
        if orientation < 0 or orientation >= ParticleLattice.NUM_ORIENTATIONS:
            raise ValueError("Invalid orientation index.")

        # Calculate new position based on orientation
        if orientation == self.layer_indices["up"]:
            new_x, new_y = x, (y - 1) % self.height
        elif orientation == self.layer_indices["down"]:
            new_x, new_y = x, (y + 1) % self.height
        elif orientation == self.layer_indices["left"]:
            new_x, new_y = (x - 1) % self.width, y
        elif orientation == self.layer_indices["right"]:
            new_x, new_y = (x + 1) % self.width, y

        return (new_x, new_y)

    def is_obstacle(self, x: int, y: int) -> bool:
        """
        Check if a cell is an obstacle.

        :param x: x-coordinate of the lattice.
        :type x: int
        :param y: y-coordinate of the lattice.
        :type y: int
        :return: True if the cell is an obstacle, False otherwise.
        :rtype: bool
        """
        return (
            "obstacles" in self.layer_indices
            and self.griglia[self.layer_indices["obstacles"], y, x]
        )

    def is_sink(self, x: int, y: int) -> bool:
        """
        Check if a cell is a sink.

        :param x: x-coordinate of the lattice.
        :type x: int
        :param y: y-coordinate of the lattice.
        :type y: int
        :return: True if the cell is a sink, False otherwise.
        :rtype: bool
        """
        return (
            "sinks" in self.layer_indices
            and self.griglia[self.layer_indices["sinks"], y, x]
        )

    def get_particle_orientation(self, x: int, y: int) -> int:
        """
        Get the orientation of a particle at (x, y).

        :param x: x-coordinate of the particle.
        :type x: int
        :param y: y-coordinate of the particle.
        :type y: int
        :return: The orientation of the particle.
        :rtype: int
        :raises ValueError: If no particle is found at the given location.
        """
        # If no particle is found at the given location, raise a value error
        if self.is_empty(x, y):
            raise ValueError("No particle found at the given location.")

        # Get the orientation of the particle
        orientation = self.particles[:, y, x].nonzero(as_tuple=True)[0]

        return orientation.item()

    def move_particle(self, x: int, y: int) -> bool:
        """
        Move a particle at (x, y) with a given orientation to the new position determined by its current orientation.
        :param x: Current x-coordinate of the particle.
        :param y: Current y-coordinate of the particle.
        :return: True if the particle was moved successfully, False otherwise.
        :rtype: bool
        :raises ValueError: If no particle is found at the given location.
        """
        # Check if the particle exists at the given location
        if self.is_empty(x, y):
            print(self)
            raise ValueError("No particle found at the given location. x=%d, y=%d" %(x,y))

        # Get the current orientation of the particle at (x, y)
        orientation = self.get_particle_orientation(x, y)

        # Get the expected position of the particle
        new_x, new_y = self.get_target_position(x, y, orientation)

        # Check if the new position is occupied or is an obstacle
        if self.is_obstacle(new_x, new_y) or not self.is_empty(new_x, new_y):
            warnings.warn(
                "Cannot move particle to the target position as there is an obstacle or another particle there.",
                stacklevel=2,
            )
            return False

        # Check if the new position is a sink, if so remove the particle
        if self.is_sink(new_x, new_y):
            self.remove_particle(x, y)
            return True

        # Move the particle
        self.remove_particle(x, y)
        #print(sum(self.griglia[:]))
        self.add_particle(new_x, new_y, orientation)        

        return True

    
    def reorient_particle(self, x: int, y: int, new_orientation: int) -> bool:
        """
        Reorient a particle at (x, y) to a new orientation.

        :param x: x-coordinate of the particle.
        :param y: y-coordinate of the particle.
        :param new_orientation: The new orientation index for the particle.
        :return: True if the particle was reoriented successfully, False otherwise.
        """
        # Raise an index error if the new orientation is out of bounds
        if new_orientation < 0 or new_orientation >= ParticleLattice.NUM_ORIENTATIONS:
            raise IndexError(f"Orientation index {new_orientation} is out of bounds.")

        # Get the current orientation of the particle at (x, y)
        current_orientation = self.get_particle_orientation(x, y)

        # If the new orientation is the same as the current one, return False
        if current_orientation == new_orientation:
            return False

        # Reorient the particle
        self.remove_particle(x, y)
        self.add_particle(x, y, new_orientation)

        return True

    def get_statistics(self) -> dict:
        """
        Compute various statistics of the lattice state.

        :return: Statistics of the current lattice state.
        :rtype: dict
        """
        # Sum only the first NUM_ORIENTATIONS layers to get the number of particles
        #num_particles = self.griglia[: self.NUM_ORIENTATIONS].sum().item()
        num_particles = self.particles[:].sum().item()
        density = num_particles / (self.width * self.height)  # Density of particles
        order_parameter = (
            self.compute_order_parameter()
        )  # Order parameter as defined before

        # Count the number of particles for each orientation
        #orientation_counts = torch.sum(
        #    self.griglia[: self.NUM_ORIENTATIONS], dim=(1, 2)
        #).tolist()
        orientation_counts = torch.sum(
            self.particles, dim=(1, 2)
        ).tolist()

        stats = {
            "number_of_particles": num_particles,
            "density": density,
            "order_parameter": order_parameter,
            "orientation_counts": orientation_counts,
            # Include other statistics as needed
        }

        return stats

    def compute_order_parameter(self):
        """
        Compute the order parameter as the magnitude of the average orientation vector.

        :return: The order parameter of the lattice.
        :rtype: float
        """
        # Define unit vectors for each orientation
        orientation_vectors = torch.tensor(
            [[0, 1], [0, -1], [-1, 0], [1, 0]], dtype=torch.float32
        )

        # Initialize the sum of orientation vectors
        orientation_vector_sum = torch.zeros(2, dtype=torch.float32)

        # Sum up orientation vectors for all particles
        for i, ori_vec in enumerate(orientation_vectors):
            num_particles = (
                #self.griglia[i].sum().item()
                self.particles[i].sum().item()
            )  # Count number of particles with this orientation
            orientation_vector_sum += num_particles * ori_vec

        # Calculate the average orientation vector
        total_particles = self.particles.sum().item()
        if total_particles == 0:
            return 0.0  # Avoid division by zero if there are no particles

        average_orientation_vector = orientation_vector_sum / total_particles

        # Calculate the magnitude of the average orientation vector
        order_parameter = torch.norm(average_orientation_vector, p=2)

        return order_parameter.item()
