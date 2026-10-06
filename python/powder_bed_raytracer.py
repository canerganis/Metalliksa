import numpy as np
import warp as wp
import time
import os

# Set HOME environment variable correctly for Windows if missing
os.environ.setdefault("HOME", os.environ.get("USERPROFILE", ""))

_wp_initialized = False

def create_powder_bed_mesh(num_particles=60, radius_um=15.0, bed_width_um=150.0):
    import trimesh
    # Deterministic hexagonal grid packing of spheres (ideal theoretical powder bed)
    points = []
    indices = []
    
    # Base plate (flat square)
    w = bed_width_um / 2.0
    base_pts = np.array([[-w, -w, 0], [w, -w, 0], [w, w, 0], [-w, w, 0]])
    base_idx = np.array([[0, 1, 2], [0, 2, 3]])
    points.append(base_pts)
    indices.append(base_idx)
    
    # Particles
    sphere = trimesh.creation.icosphere(subdivisions=2, radius=radius_um)
    v_base = sphere.vertices
    f_base = sphere.faces
    
    # Hexagonal grid calculation
    side_len = int(np.ceil(np.sqrt(num_particles)))
    spacing = radius_um * 2.0
    
    count = 0
    v_offset = 4
    for i in range(side_len):
        for j in range(side_len):
            if count >= num_particles:
                break
            # Hexagonal offset
            x = (i - side_len/2.0) * spacing + (spacing/2.0 if j % 2 else 0)
            y = (j - side_len/2.0) * spacing * np.sqrt(3)/2.0
            z = radius_um
            
            p_moved = v_base + np.array([x, y, z])
            points.append(p_moved)
            indices.append(f_base + v_offset)
            v_offset += len(v_base)
            count += 1
            
    return np.vstack(points), np.vstack(indices).flatten().astype(np.int32)

@wp.kernel
def laser_powder_raytrace(
    mesh_id: wp.uint64,
    num_rays: int,
    beam_radius_um: float,
    base_absorptivity: float,
    bed_top_z: float,
    max_bounces: int,
    min_power: float,
    absorbed_energy: wp.array(dtype=float),
    escaped_energy: wp.array(dtype=float),
    truncated_energy: wp.array(dtype=float),
    penetration_depth: wp.array(dtype=float),
    bounce_counts: wp.array(dtype=int)
):
    tid = wp.tid()
    if tid >= num_rays:
        return

    u1 = wp.sin(float(tid) * 12.9898) * 43758.5453
    u1 = u1 - wp.floor(u1)
    u2 = wp.cos(float(tid) * 78.233) * 43758.5453
    u2 = u2 - wp.floor(u2)

    # Gaussian TEM00 beam, I ~ exp(-2 r^2 / w^2) with w = beam_radius_um (1/e^2 radius):
    # inverse CDF r = w sqrt(-ln(1 - u) / 2) (same sampler as lpbf_keyhole_raytracing.py).
    r = beam_radius_um * wp.sqrt(-0.5 * wp.log(wp.max(1.0 - u1, 1.0e-7)))
    theta = 2.0 * 3.1415926535 * u2
    x = r * wp.cos(theta)
    y = r * wp.sin(theta)
    z = 80.0

    ray_orig = wp.vec3(x, y, z)
    ray_dir = wp.vec3(0.0, 0.0, -1.0)

    remaining_power = float(1.0)
    total_absorbed = float(0.0)
    deepest_z = float(z)
    bounces = int(0)
    curr_orig = ray_orig
    curr_dir = ray_dir

    escaped = float(0.0)
    in_flight = int(1)
    for b in range(max_bounces):
        if in_flight == 1 and remaining_power > min_power:
            query = wp.mesh_query_ray(mesh_id, curr_orig, curr_dir, 1000.0)

            if not query.result:
                # No further intersection: the remaining power leaves the bed.
                escaped = remaining_power
                remaining_power = float(0.0)
                in_flight = 0
            else:
                bounces += 1
                hit_pos = curr_orig + curr_dir * query.t
                hit_normal = wp.normalize(query.normal)

                if hit_pos[2] < deepest_z:
                    deepest_z = hit_pos[2]

                cos_theta = -wp.dot(curr_dir, hit_normal)
                if cos_theta < 0.0:
                    hit_normal = -hit_normal
                    cos_theta = -cos_theta

                absorbed_fraction = base_absorptivity * (1.0 + 0.3 * (1.0 - cos_theta))
                if absorbed_fraction > 0.95:
                    absorbed_fraction = 0.95

                absorbed_here = remaining_power * absorbed_fraction
                total_absorbed += absorbed_here
                remaining_power -= absorbed_here

                reflect_dir = wp.normalize(curr_dir + hit_normal * (2.0 * cos_theta))
                curr_orig = hit_pos + reflect_dir * 0.1
                curr_dir = reflect_dir

    absorbed_energy[tid] = total_absorbed
    escaped_energy[tid] = escaped
    # Power still bouncing at the bounce cap or below min_power: neither absorbed nor escaped.
    truncated_energy[tid] = remaining_power
    # Depth below the bed top (sphere tops at z = 2 r), not below the launch plane.
    penetration_depth[tid] = wp.max(0.0, bed_top_z - deepest_z)
    bounce_counts[tid] = bounces

_cached_mesh = None

def get_or_create_mesh():
    global _cached_mesh
    if _cached_mesh is None:
        points_np, indices_np = create_powder_bed_mesh()
        _cached_mesh = wp.Mesh(
            points=wp.array(points_np, dtype=wp.vec3, device="cuda:0"),
            indices=wp.array(indices_np, dtype=int, device="cuda:0")
        )
    return _cached_mesh

MAX_BOUNCES = 50          # converged: 50 and 200 bounces agree (Wave B KS-4 check)
MIN_REMAINING_POWER = 1.0e-6
PARTICLE_RADIUS_UM = 15.0  # create_powder_bed_mesh default; bed top at z = 2 r


def calculate_powder_bed_absorptivity(beam_radius_um: float, base_absorptivity: float, num_rays: int = 100000,
                                      max_bounces: int = MAX_BOUNCES,
                                      min_remaining_power: float = MIN_REMAINING_POWER) -> dict:
    global _wp_initialized
    if not _wp_initialized:
        wp.init()
        _wp_initialized = True

    mesh = get_or_create_mesh()

    absorbed_energy = wp.zeros(shape=num_rays, dtype=float, device="cuda:0")
    escaped_energy = wp.zeros(shape=num_rays, dtype=float, device="cuda:0")
    truncated_energy = wp.zeros(shape=num_rays, dtype=float, device="cuda:0")
    penetration_depth = wp.zeros(shape=num_rays, dtype=float, device="cuda:0")
    bounce_counts = wp.zeros(shape=num_rays, dtype=int, device="cuda:0")

    wp.launch(
        kernel=laser_powder_raytrace,
        dim=num_rays,
        inputs=[mesh.id, num_rays, float(beam_radius_um), float(base_absorptivity), 2.0 * PARTICLE_RADIUS_UM,
                int(max_bounces), float(min_remaining_power), absorbed_energy, escaped_energy, truncated_energy,
                penetration_depth, bounce_counts],
        device="cuda:0"
    )
    wp.synchronize()

    abs_np = absorbed_energy.numpy()
    bounces_np = bounce_counts.numpy()
    depth_np = penetration_depth.numpy()

    avg_absorption = np.mean(abs_np)
    esc_np = escaped_energy.numpy()
    # A ray with no hit at all fell outside the finite bed (geometry artefact, as in
    # lpbf_keyhole_raytracing.py): reported as missed, not as reflected (escaped) power.
    missed_fraction = float(np.sum(esc_np[bounces_np == 0]) / num_rays)
    escaped_fraction = float(np.sum(esc_np[bounces_np > 0]) / num_rays)
    truncated_fraction = float(np.mean(truncated_energy.numpy()))
    avg_bounces = np.mean(bounces_np)
    multi_reflection_rays = np.sum(bounces_np > 1) / num_rays
    avg_depth = np.mean(depth_np[bounces_np > 0])

    return {
        "effective_absorptivity": float(avg_absorption),
        "average_bounces": float(avg_bounces),
        "multi_reflection_fraction": float(multi_reflection_rays),
        "average_penetration_depth_um": float(avg_depth),
        "penetration_depth_reference": "bed top (z = 2 * particle radius)",
        "escaped_fraction": escaped_fraction,
        "missed_fraction": missed_fraction,
        "truncated_fraction": truncated_fraction,
        "energy_closure_residual": float(abs(1.0 - float(avg_absorption) - escaped_fraction - missed_fraction - truncated_fraction)),
        "max_bounces": int(max_bounces),
        "beam_profile": "gaussian-1/e2",
    }
