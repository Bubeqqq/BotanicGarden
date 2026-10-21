#[compute]
#version 450

layout(local_size_x = 8, local_size_y = 4, local_size_z = 8) in;

layout(set = 0, binding = 0, rgba16i) uniform restrict readonly iimage3D input_img;
layout(set = 0, binding = 1, rgba16i) uniform restrict writeonly iimage3D output_img;

layout(push_constant, std430) uniform Params {
    uint frame_seed;
} params;

ivec4 get_voxel(ivec3 pos, ivec3 grid_size) {
    if (pos.x < 0 || pos.x >= grid_size.x ||
        pos.y < 0 || pos.y >= grid_size.y ||
        pos.z < 0 || pos.z >= grid_size.z) {
        return ivec4(0, 0, 0, 0);
    }
    return imageLoad(input_img, pos);
}

uint pcg_hash(uint seed) {
    uint state = seed * 747796405u + 2891336453u;
    uint word = ((state >> ((state >> 28u) + 4u)) ^ state) * 277803737u;
    return (word >> 22u) ^ word;
}

float rand_fast(uvec3 pos) {
    uint seed = pos.x * 1664525u + pos.y * 1013904223u + pos.z * 374761393u + params.frame_seed * 2246822519u;;
    return float(pcg_hash(seed)) * (1.0 / 4294967295.0);
}

ivec4 check_voxels_on_Y_axis(int y, int index, ivec4[3][3][3] neighbors){
    for(int x = 0; x < 3; x++){
        for(int z = 0; z < 3; z++){
            if(neighbors[x][y][z].r == index){
                return neighbors[x][y][z];
            }
        }
    }
    return ivec4(0, 0, 0, 0);
}

void main() {
    ivec3 position = ivec3(gl_GlobalInvocationID.xyz);
    ivec3 grid_size = imageSize(input_img);

    if (position.x >= grid_size.x || position.y >= grid_size.y || position.z >= grid_size.z) {
        return;
    }
    
    ivec4 neighbors[3][3][3];

    for (int dx = -1; dx <= 1; dx++) {
        for (int dy = -1; dy <= 1; dy++) {
            for (int dz = -1; dz <= 1; dz++) {
                ivec3 check_pos = position + ivec3(dx, dy, dz);
                ivec4 val = get_voxel(check_pos, grid_size);

                neighbors[dx + 1][dy + 1][dz + 1] = val;
            }
        }
    }

    ivec4 current_value = neighbors[1][1][1];

    ivec4 up    = neighbors[1][2][1]; // y + 1
    ivec4 down  = neighbors[1][0][1]; // y - 1
    ivec4 right = neighbors[2][1][1]; // x + 1
    ivec4 left  = neighbors[0][1][1]; // x - 1
    ivec4 front = neighbors[1][1][2]; // z + 1
    ivec4 back  = neighbors[1][1][0]; // z - 1
    
    ivec4 new_value = ivec4(current_value.r, current_value.g, current_value.b ,current_value.a);
    
    if(current_value.r == 1){
        if(check_voxels_on_Y_axis(1, 4, neighbors).r != 0)
        {
            new_value.r = 5;
        }

        if(check_voxels_on_Y_axis(2, 4, neighbors).r != 0)
        {
            new_value.r = 5;
        }
        
        if(check_voxels_on_Y_axis(1, 2, neighbors).r == 0){
            ivec4 bottom = check_voxels_on_Y_axis(0, 2, neighbors);
            if(bottom.r != 0){
                float r = rand_fast(gl_GlobalInvocationID.xyz);

                if(r < 0.001f){
                    new_value.r = 2;
                    new_value.b = bottom.b + 1;
                }else if(r > 1 - (0.0001f * float(current_value.b))){
                    new_value.r = 4;
                }
            }
        }
    }else if(current_value.r == 2){
        if(check_voxels_on_Y_axis(2, 2, neighbors).r != 0){
            float r = rand_fast(gl_GlobalInvocationID.xyz);
            
            if(r < 0.003f * float(current_value.b)){
                new_value.r = 3;
            }
        }

        if(check_voxels_on_Y_axis(2, 4, neighbors).r != 0)
        {
            new_value.r = 3;
        }
    }

    imageStore(output_img, position, new_value);
}