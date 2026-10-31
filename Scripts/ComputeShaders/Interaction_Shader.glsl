#[compute]
#version 450

layout(local_size_x = 1, local_size_y = 1, local_size_z = 1) in;

// Format RGBA16UI idealnie pasuje do Twojego R16G16B16A16Uint z C#
layout(rgba16ui, set = 0, binding = 0) uniform uimage3D voxel_map;

// Układ pamięci w std430 wymusza wyrównanie takie same, jak w Twojej strukturze C#
layout(push_constant, std430) uniform Params {
    vec3 ray_start;     
    float max_dist;     
    vec3 ray_dir;       
    int action_type;    
} params;

void main() {
    // 1. Zabezpieczenie kierunku przed dzieleniem przez idealne 0
    vec3 ray_dir = params.ray_dir;
    if (length(ray_dir) < 0.001) return; 
    ray_dir = normalize(ray_dir); 

    vec3 start_pos = params.ray_start;
    vec3 map_pos = floor(start_pos);
    vec3 ray_step = sign(ray_dir);
    
    // Używamy max(), aby nigdy nie podzielić przez zero (1e-6 to bardzo mała liczba)
    vec3 delta_dist = abs(1.0 / max(abs(ray_dir), vec3(1e-6))); 
    
    vec3 side_dist = (sign(ray_dir) * (map_pos - start_pos) + (sign(ray_dir) * 0.5) + 0.5) * delta_dist;

    ivec3 previous_pos = ivec3(map_pos);
    ivec3 grid_size = imageSize(voxel_map);

    for (int i = 0; i < int(params.max_dist); i++) {
        ivec3 imap_pos = ivec3(map_pos);
        
        // Zamiast przerywać pętlę (break), po prostu sprawdzamy, czy w danym kroku jesteśmy wewnątrz
        bool is_inside_grid = all(greaterThanEqual(imap_pos, ivec3(0))) && all(lessThan(imap_pos, grid_size));

        if (is_inside_grid) {
            uvec4 state = imageLoad(voxel_map, imap_pos);
            
            if (state.r > 1u) { 
                // Trafiliśmy w twardy blok!
                if (params.action_type == 0) {
                    // LPM: Zniszcz blok (ustaw na powietrze = 0)
                    imageStore(voxel_map, imap_pos, uvec4(0u, 0u, 0u, 0u));
                } 
                else if (params.action_type > 0) {
                    // PPM: Postaw nowy blok na miejscu poprzedniego (wolnego) woksela
                    if (all(greaterThanEqual(previous_pos, ivec3(0))) && all(lessThan(previous_pos, grid_size))) {
                        imageStore(voxel_map, previous_pos, uvec4(uint(params.action_type), 1u, 1u, 1u));
                    }
                }
                break; // Kończymy raycast po pierwszej udanej akcji
            }
        }

        previous_pos = imap_pos;

        // Skok do następnego woksela (algorytm DDA)
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