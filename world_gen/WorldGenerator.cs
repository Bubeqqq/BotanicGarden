using Godot;
using System;

namespace BotanicGarden.WorldGen;

public static class WorldGenerator
{
    // 	private const int _gridWidth = 256, _gridDepth = 256, _gridHeight = 128;
	// private const int _minTerrainHeight = 10, _maxTerrainHeight = 60;
	// private const int _terrainHeight = 
    public static ushort[] Generate(
        int gridWidth,
        int gridDepth,
        int gridHeight,
        int minTerrainHeight,
        int maxTerrainHeight,
        float waterPercentage
    )
    {
        int VoxelCount = gridWidth * gridDepth * gridHeight;
        int terrainHeight = maxTerrainHeight - minTerrainHeight;
        int waterLevel = minTerrainHeight + (int)Math.Floor(terrainHeight * waterPercentage);

        var world = new ushort[VoxelCount * 4];

        // Generate Height Map
        var map = DiamondSquare.Generate(gridWidth, gridDepth, DiamondSquare.StartIterForRegionSize(gridWidth, gridDepth, 128));
        DiamondSquare.Standardize(map, gridWidth, gridDepth, .175f);

        // Generate Landmass and Water
        for (var i = 0; i < VoxelCount; i++)
        {
            var x = i % gridWidth;
            var y = i / gridWidth % gridHeight;
            var z = i / (gridWidth * gridHeight);
            var idx = i * 4;

            var surfaceLevel = (int)(map[x, z] * terrainHeight) + minTerrainHeight;

            if (y <= surfaceLevel)
            {
                // set dirt
                world[idx] = 6144;
            }
            else if (y <= waterLevel)
            {
                // set water
                world[idx] = 8193;
            }
            else
            {
                world[idx] = 0;
            }
        }

        // Generate Perimeter Fence
        // Todo: implement

        // Generate Lampposts
        // Todo: implement

        // Scatter rocks
        // Todo: implement

        // Scatter seeds
        // Todo: implement

        var whichFlower = false;
        for (var i = 0; i < VoxelCount; i++)
        {
            var x = i % gridWidth;
            var y = (i / gridWidth) % gridHeight;
            var z = i / (gridWidth * gridHeight);
            var idx = i * 4;

            if ( y == (int)(map[x, z] * terrainHeight) + minTerrainHeight + 1 && GD.Randf() < 0.003f)
            {
                world[idx] = whichFlower ? (ushort)4096 : (ushort)4101;
                whichFlower = !whichFlower;
            }
            
            // if(y <= 15)
            // 	world[idx] = 6144;
            // else if (y == 16 && x % 16 == 0 && z % 16 == 0)
            // {
            //     //initialData[idx] = whichFlower ? (short)4096 : (short)4101;
            //     whichFlower = !whichFlower;
            // }
            // else
            // 	world[idx] = 0;
                    
            world[idx + 1] = 1;
            world[idx + 2] = 1;
            world[idx + 3] = 1;
        }

        return world;
    }
}