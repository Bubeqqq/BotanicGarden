shader_type spatial;
render_mode unshaded, cull_front;

uniform isampler3D image : filter_nearest, repeat_disable;
uniform ivec3 grid_size = ivec3(128, 128, 128);
uniform vec3 box_size = vec3(6.4, 6.4, 6.4);

uniform bool transparent_soils = false;
uniform bool show_territories = false;

uniform sampler2D color_palette : source_color;
uniform usampler2D highlight_data;
varying vec3 local_camera_pos;
varying vec3 local_vertex_pos;
varying flat ivec3 chunk_global_origin;

bool is_solid(int state) {
    if (state <= 1) {
        return false;
    }
    
    return true;
}

void vertex() {
    mat4 inverse_pos = inverse(MODEL_MATRIX);

    vec3 cam_world = INV_VIEW_MATRIX[3].xyz;
    vec3 local_camera = (inverse_pos * vec4(cam_world, 1.0)).xyz;
    
    local_camera_pos = (local_camera / box_size + 0.5) * vec3(grid_size);
    local_vertex_pos = (VERTEX / box_size + 0.5) * vec3(grid_size);

    vec3 world_pos = MODEL_MATRIX[3].xyz;
    vec3 chunk_corner = world_pos - (box_size / 2.0);
    chunk_global_origin = ivec3(round(chunk_corner / box_size)) * grid_size;
}

//Slab Method
vec2 intersect_box(vec3 orig, vec3 inv_dir, vec3 b_min, vec3 b_max) {
    vec3 t0 = (b_min - orig) * inv_dir;
    vec3 t1 = (b_max - orig) * inv_dir;
    vec3 tmin = min(t0, t1);
    vec3 tmax = max(t0, t1);
    float near = max(max(tmin.x, tmin.y), tmin.z);
    float far = min(min(tmax.x, tmax.y), tmax.z);
    return vec2(near, far);
}

bool check_highlight(ivec3 voxel_pos, uvec4 hl) {
    if (hl.w == 0u) return false;

    ivec3 center = ivec3(hl.xyz);
    int r = int(hl.w) - 1;

    int dx = voxel_pos.x - center.x;
    int dz = voxel_pos.z - center.z;
    int dy = abs(voxel_pos.y - center.y);

    if (dy <= r + 2) {
        int dist_sq = dx * dx + dz * dz;
        int r_sq = r * r;

        if (dist_sq <= r_sq) {
            bool is_center = (dist_sq == 0);
            bool is_border =
            ((dx + 1) * (dx + 1) + dz * dz > r_sq) ||
                    ((dx - 1) * (dx - 1) + dz * dz > r_sq) ||
                    (dx * dx + (dz + 1) * (dz + 1) > r_sq) ||
                    (dx * dx + (dz - 1) * (dz - 1) > r_sq);

            return is_center || is_border;
        }
    }
    return false;
}

vec4 add_colors(vec4 accum, vec4 src) {
    float weight = src.a * (1.0 - accum.a);
    accum.rgb += src.rgb * weight;
    accum.a += weight;
    return accum;
}

vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

vec3 high_contrast_color(uint idx) {
    const float GOLDEN_RATIO_CONJUGATE = 0.61803398875;
    
    float hue = fract(float(idx) * GOLDEN_RATIO_CONJUGATE);
    
    float parity = float(idx & 1u);
    float sat = mix(0.85, 1.0, 1.0 - parity * 0.5);
    float val = mix(1.0, 0.78, parity);

    return hsv2rgb(vec3(hue, sat, val));
}

void fragment() {
    vec3 ray_dir = normalize(local_vertex_pos - local_camera_pos);
    vec3 inv_dir = 1.0 / max(abs(ray_dir), vec3(1e-5)) * sign(ray_dir);

    vec2 hit = intersect_box(local_camera_pos, inv_dir, vec3(0.0), vec3(grid_size));

    if (hit.x > hit.y || hit.y < 0.0) {
        discard;
    }

    float start = max(hit.x, 0.0);
    vec3 current_pos = local_camera_pos + ray_dir * (start + 0.001);

    ivec3 map_pos = clamp(ivec3(floor(current_pos)), ivec3(0), grid_size - 1);
    vec3 delta_dist = abs(inv_dir);
    ivec3 ray_step = ivec3(sign(ray_dir));
    vec3 side_dist = (sign(ray_dir) * (vec3(map_pos) - current_pos) + (sign(ray_dir) * 0.5) + 0.5) * delta_dist;
    
    vec3 mask = vec3(0.0, 1.0, 0.0);
    if (hit.x > 0.0) {
        vec3 t0 = (vec3(0.0) - local_camera_pos) * inv_dir;
        vec3 t1 = (vec3(grid_size) - local_camera_pos) * inv_dir;
        vec3 tmin = min(t0, t1);
        mask = step(tmin.yzx, tmin.xyz) * step(tmin.zxy, tmin.xyz);
    }

    uvec4 hl = texelFetch(highlight_data, ivec2(0, 0), 0);
    vec4 actual_color = vec4(0.0);

    for (int i = 0; i < 384; i++) {
        if (any(lessThan(vec3(map_pos), vec3(0.0))) || any(greaterThanEqual(vec3(map_pos), vec3(grid_size)))) {
            break;
        }

        ivec3 global_voxel = chunk_global_origin + map_pos;
        ivec4 voxel = texelFetch(image, global_voxel, 0);
        int state = voxel.r;
        int g_factor = voxel.g ;
        
        if (is_solid(state)) {
            int x = state % 256;
            int y = state / 256;
            vec4 color = texelFetch(color_palette, ivec2(x, y), 0);
            int type = (state >> 11) & 0x1F;
            
            if(type == 3){ // Toogle for transparent soils
                if(transparent_soils){
                    color.a = 0.01;
                }
                
                //Change color for plant territories
                if(g_factor > 1 && show_territories){
                    color = vec4(high_contrast_color(uint(g_factor)), color.a);
                }
            }
            
            if (color.a > 0.0) {
                float shade = mask.x * 0.8 + mask.y * 1.0 + mask.z * 0.6;
                color.rgb *= shade;
                
                if (check_highlight(global_voxel, hl)) {
                    color.rgb = mix(color.rgb, vec3(1.0, 1.0, 0.5), 0.35);
                }
                
                actual_color = add_colors(actual_color, color);
                
                if (actual_color.a >= 0.995) {
                    actual_color.a = 1.0;
                    break;
                }
            }
        }

        mask = step(side_dist.xyz, min(side_dist.yzx, side_dist.zxy));
        side_dist += mask * delta_dist;
        map_pos += ivec3(mask) * ray_step;
    }

    if (actual_color.a <= 0.001) {
        discard;
    }
    
    ALBEDO = actual_color.rgb / actual_color.a;
    ALPHA = actual_color.a;
}
