#[compute]
#version 450

layout(local_size_x = 8, local_size_y = 4, local_size_z = 8) in;

layout(set = 0, binding = 0, rgba16ui) uniform restrict readonly uimage3D input_img;

layout(set = 0, binding = 1, std430) restrict buffer DataBuffer {
    int dataArray[];
};

uvec4 get_voxel(ivec3 pos, ivec3 grid_size) {
    if (pos.x < 0 || pos.x >= grid_size.x ||
        pos.y < 0 || pos.y >= grid_size.y ||
        pos.z < 0 || pos.z >= grid_size.z) {
        return uvec4(0, 0, 0, 0);
    }
    return imageLoad(input_img, pos);
}

void main() {
    ivec3 position = ivec3(gl_GlobalInvocationID.xyz);
    ivec3 grid_size = imageSize(input_img);

    if (position.x >= grid_size.x || position.y >= grid_size.y || position.z >= grid_size.z) { //if voxel is out of bounds
        return;
    }

    uvec4 current_value = get_voxel(position, grid_size);
    uint type = (current_value.r >> 11u) & 0x1Fu; //type of voxel
    
    if(type == 2) // Voxel is type of flower
    {
        atomicAdd(dataArray[current_value.g], 1);
    }
}