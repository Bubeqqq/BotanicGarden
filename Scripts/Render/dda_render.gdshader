shader_type spatial;
render_mode unshaded, cull_front;

uniform isampler3D image : filter_nearest, repeat_disable;
uniform ivec3 grid_size = ivec3(128, 128, 128);
uniform vec3 box_size = vec3(6.4, 6.4, 6.4);

varying vec3 local_camera_pos;
varying vec3 local_vertex_pos;
varying flat ivec3 chunk_global_origin;

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

    vec3 mask = vec3(0.0);
    int hit_state = 0;
    
    for (int i = 0; i < 384; i++) {
        if (any(lessThan(vec3(map_pos), vec3(0.0))) || any(greaterThanEqual(vec3(map_pos), vec3(grid_size)))) {
            break;
        }

        int state = texelFetch(image, chunk_global_origin + map_pos, 0).r;
        if (state > 1) { 
            hit_state = state;
            break;
        }

        mask = step(side_dist.xyz, min(side_dist.yzx, side_dist.zxy));
        side_dist += mask * delta_dist;
        map_pos += ivec3(mask) * ray_step;
    }

    if (hit_state <= 1) {
        discard;
    }

    vec3 color = vec3(1.0);
    if (hit_state == 2) {
        color = vec3(0.0, 1.0, 0.0);
    } else if (hit_state == 3) {
        color = vec3(0.0, 0.7, 0.2);
    } else if (hit_state == 4) {
        color = vec3(1.0, 1.0, 0.0);
    } else if (hit_state == 5) {
        color = vec3(1.0, 1.0, 1.0);
    } else if (hit_state == 6) {
        color = vec3(0.59, 0.29, 0.0);
    } else {
        color = vec3(1.0, 0.0, 0.0);
    }
    
    //rainbow color
    //vec3 color = vec3(float(hit_state) / 255.0, 0.0, 1.0 - float(hit_state) / 255.0);

    float shade = mask.x * 0.8 + mask.y * 1.0 + mask.z * 0.6;
    ALBEDO = color;
}