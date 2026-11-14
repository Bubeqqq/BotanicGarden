#[compute]
#version 450

struct MyDataStruct {
    ivec4 packedData;
};

layout(local_size_x = 8, local_size_y = 4, local_size_z = 8) in;

layout(set = 0, binding = 0, rgba16ui) uniform restrict readonly uimage3D input_img;
layout(set = 0, binding = 1, rgba16ui) uniform restrict writeonly uimage3D output_img;

layout(set = 0, binding = 2, std430) restrict buffer DataBuffer {
    MyDataStruct dataArray[];
};

layout(set = 0, binding = 3, std430) restrict coherent buffer PlantCounterBuffer {
    uint next_plant_id;
};

layout(push_constant, std430) uniform Params {
	uint frame_seed;
} params;

// Tools
#include "res://Scripts/ComputeShaders/Common_Utils.glslinc"

// Shaders for computations
#include "res://Scripts/ComputeShaders/Air_Shader.glslinc"
#include "res://Scripts/ComputeShaders/Flower_Shader.glslinc"
#include "res://Scripts/ComputeShaders/Soil_Shader.glslinc"
#include "res://Scripts/ComputeShaders/Falling_Blocks_Shader.glslinc"

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
    uint index = current_value.r; //index in that type
    
    uvec4 new_value = uvec4(current_value.r, current_value.g, current_value.b ,current_value.a);
    
    //Types that don't requeire scanning
    
    if(type == 1){ //statics
        imageStore(output_img, position, new_value);
        return;
    }
    
    //types that requeire scanning 
    uvec4 neighbors[3][3][3];

    for (int dx = -1; dx <= 1; dx++) {
        for (int dy = -1; dy <= 1; dy++) {
            for (int dz = -1; dz <= 1; dz++) {
                ivec3 check_pos = position + ivec3(dx, dy, dz);
                uvec4 val = get_voxel(check_pos, grid_size);


                neighbors[dx + 1][dy + 1][dz + 1] = val;
            }
        }
    }
    //11111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111
    if(type == 0){ // Special voxels
        if(index == 0) // Air
            new_value = calculate_air(neighbors, gl_GlobalInvocationID.xyz, params.frame_seed);
    }else if(type == 2){ // Plants
        new_value = calculate_flower(neighbors, gl_GlobalInvocationID.xyz, params.frame_seed);
    }else if(type == 3){ // Soil
        new_value = calculate_soil(neighbors, gl_GlobalInvocationID.xyz, params.frame_seed);
    }else if(type == 4){ // Falling Blocks
        new_value = calculate_falling_blocks(neighbors, gl_GlobalInvocationID.xyz, params.frame_seed);
    }

    imageStore(output_img, position, new_value);
}
