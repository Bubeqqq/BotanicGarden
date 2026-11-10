#[compute]
#version 450

layout(local_size_x = 1, local_size_y = 1, local_size_z = 1) in;

layout(rgba16ui, set = 0, binding = 0) uniform uimage3D voxel_map;
layout(rgba16ui, set = 0, binding = 1) uniform writeonly uimage2D highlight_map; 

layout(push_constant, std430) uniform Params {
    vec3 ray_start;     
    float max_dist;     
    vec3 ray_dir;       
    int action_type;    
    int radius;
    float seed;
    float density;      
    float pad0;
} params;

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453123);
}

void main() {
    imageStore(highlight_map, ivec2(0, 0), uvec4(0u, 0u, 0u, 0u));

    vec3 ray_dir = params.ray_dir;
    if (length(ray_dir) < 0.001) return; 
    ray_dir = normalize(ray_dir); 

    vec3 start_pos = params.ray_start;
    vec3 map_pos = floor(start_pos);
    vec3 ray_step = sign(ray_dir);
    
    vec3 delta_dist = abs(1.0 / max(abs(ray_dir), vec3(1e-6))); 
    vec3 side_dist = (sign(ray_dir) * (map_pos - start_pos) + (sign(ray_dir) * 0.5) + 0.5) * delta_dist;

    ivec3 previous_pos = ivec3(map_pos);
    ivec3 grid_size = imageSize(voxel_map);

    for (int i = 0; i < int(params.max_dist); i++) {
        ivec3 imap_pos = ivec3(map_pos);
        bool is_inside_grid = all(greaterThanEqual(imap_pos, ivec3(0))) && all(lessThan(imap_pos, grid_size));

        if (is_inside_grid) {
            uvec4 state = imageLoad(voxel_map, imap_pos);
            
            if (state.r > 1u) { 

                imageStore(highlight_map, ivec2(0, 0), uvec4(imap_pos.x, imap_pos.y, imap_pos.z, uint(params.radius + 1)));

                if (params.action_type == 0) {
                    imageStore(voxel_map, imap_pos, uvec4(0u, 0u, 0u, 0u));
                } 
                else if (params.action_type > 0) {
                    if (params.radius <= 0) {
                        if (all(greaterThanEqual(previous_pos, ivec3(0))) && all(lessThan(previous_pos, grid_size))) {
                            imageStore(voxel_map, previous_pos, uvec4(uint(params.action_type), 1u, 1u, 1u));
                        }
                    } else {
                        int r = params.radius;
                        for (int dx = -r; dx <= r; dx++) {
                            for (int dz = -r; dz <= r; dz++) {
                                if (dx*dx + dz*dz > r*r) continue;
                                
                                int place_x = imap_pos.x + dx;
                                int place_z = imap_pos.z + dz;
                                
                                if (hash(vec2(place_x, place_z) + params.seed) > params.density) continue;
                                
                                if (place_x < 0 || place_x >= grid_size.x || place_z < 0 || place_z >= grid_size.z) continue;
                                
                                int start_y = min(imap_pos.y + r + 2, grid_size.y - 1);
                                int end_y = max(imap_pos.y - r - 2, 0);
                                
                                for (int y = start_y; y >= end_y; y--) {
                                    ivec3 check_pos = ivec3(place_x, y, place_z);
                                    uvec4 column_state = imageLoad(voxel_map, check_pos);

                                    if (column_state.r > 1u) { 
                                        ivec3 target_pos = ivec3(place_x, y + 1, place_z);
                                        
                                        if (target_pos.y < grid_size.y) {
                                            uvec4 upper_state = imageLoad(voxel_map, target_pos);
                                            if (upper_state.r <= 1u) {
                                                imageStore(voxel_map, target_pos, uvec4(uint(params.action_type), 1u, 1u, 1u));
                                            }
                                        }
                                        break; 
                                    }
                                }
                            }
                        }
                    }
                }
                break; 
            }
        }

        previous_pos = imap_pos;

        if (side_dist.x < side_dist.y && side_dist.x < side_dist.z) {
            side_dist.x += delta_dist.x;
            map_pos.x += ray_step.x;
        } else if (side_dist.y < side_dist.z) {
            side_dist.y += delta_dist.y;
            map_pos.y += ray_step.y;
        } else {
            side_dist.z += delta_dist.z;
            map_pos.z += ray_step.z;
        }
    }
}