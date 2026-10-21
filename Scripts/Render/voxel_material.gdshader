shader_type spatial;

uniform isampler3D image: filter_nearest, repeat_disable;
uniform int grid_width = 4;
uniform int grid_depth = 4;
uniform int grid_height = 4;
uniform float spacing = 1.0;
uniform ivec3 chunk_size = ivec3(32, 20, 32);
uniform float voxel_size = 1.0;
uniform float chunk_spacing = 1.0f;

void vertex() {
    int index = INSTANCE_ID;

    float x = float(index % chunk_size.x);
    float y = float((index / chunk_size.x) % chunk_size.y);
    float z = float((index / (chunk_size.x * chunk_size.y)));

    vec3 local_pos = vec3(float(x), float(y), float(z));

    vec3 chunk_origin = round(MODEL_MATRIX[3].xyz / (voxel_size * spacing * chunk_spacing));

    ivec3 global_voxel = ivec3(chunk_origin + local_pos);

    if (global_voxel.x >= grid_width || global_voxel.y >= grid_height || global_voxel.z >= grid_depth) {
        VERTEX = vec3(0.0);
    } else {
        int state = texelFetch(image, global_voxel, 0).r;
        
        switch (state){
            case 1 :
                VERTEX = vec3(0.0);
                break;
            case 2:
                VERTEX += local_pos * spacing;
                COLOR = vec4(0.0, 1.0, 0.0, 1.0);
                break;
            case 3:
                VERTEX += local_pos * spacing;
                COLOR = vec4(0.0, 0.7, 0.2, 1.0);
                break;
            case 4:
                VERTEX += local_pos * spacing;
                COLOR = vec4(1.0, 1.0, 0.0, 1.0);
                break;
            case 5:
                VERTEX += local_pos * spacing;
                COLOR = vec4(1.0, 1.0, 1.0, 1.0);
                break;
        }
    }
}

void fragment() {
    ALBEDO = COLOR.rgb;
    ROUGHNESS = 0.8;
}