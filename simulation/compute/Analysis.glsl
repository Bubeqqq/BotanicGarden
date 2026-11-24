#[compute]
#version 450

struct MyDataStruct {
    uvec4 packedData;
};

layout(local_size_x = 8, local_size_y = 4, local_size_z = 8) in;

layout(set = 0, binding = 0, rgba16ui) uniform restrict readonly uimage3D input_img;

layout(set = 0, binding = 1, std430) restrict buffer DataBuffer {
    uint dataArray[];
};

layout(set = 0, binding = 2, std430) restrict buffer VoxelDataBuffer {
    MyDataStruct voxelData[];
};

uint getFlowerSpeciesID(uint index){
    uvec4 raw = voxelData[index].packedData;
    return bitfieldExtract(raw.x, 16, 16);
}

void main() {
    ivec3 position = ivec3(gl_GlobalInvocationID.xyz);
    ivec3 grid_size = imageSize(input_img);

    if (any(greaterThanEqual(position, grid_size))) {
        return;
    }

    uvec4 current_value = imageLoad(input_img, position);
    uint type = (current_value.r >> 11u) & 0x1Fu;

    if (type == 2u) {
        uint flower_id = current_value.g;
        
        uint prev = atomicAdd(dataArray[flower_id], 1u);
        
        if (prev == 0u) {
            uint species = getFlowerSpeciesID(current_value.r);
            if (species != 0u) {
                atomicOr(dataArray[flower_id], species << 21u);
            }
        }
    }
}