using Godot;
using System;
using System.Numerics;

namespace BotanicGarden.WorldGen;

public static class WorldGenerator
{
    private const ushort WATER_IDX = 8193;
    private const ushort DIRT_IDX = 6144;
    private const ushort AIR_IDX = 0;

    private static int CoordsToIndex(Vector3I coords, Vector3I gridSize)
    {
        var index = coords.X + (coords.Y  + coords.Z * gridSize.Y) * gridSize.X;
        return index;
    }

    private static Vector3I IndexToCoords(int index, Vector3I gridSize)
    {
        var x = index % gridSize.X;
        var y = index / gridSize.X % gridSize.Y;
        var z = index / (gridSize.X * gridSize.Y);
        var v = new Vector3I(x, y, z);
        return v;
    }

    private static bool BlockInBlockList(ushort block, ushort[] blockList)
    {
        foreach(var b in blockList) if (block == b) return true;
        return false;
    }

    private static bool PasteModel(ushort[] world, Vector3I gridSize, Model model, Vector3I position, ushort[] allowedSpawnBlockTypes)
    {
        if (!BlockInBlockList(world[CoordsToIndex(position-model.origin, gridSize)], allowedSpawnBlockTypes)) return false;
        // todo: implement
        return true;
    }

    public static ushort[] Generate(
        Vector3I gridSize,
        int minTerrainHeight,
        int maxTerrainHeight,
        float waterPercentage
    )
    {
        int VoxelCount = gridSize.X * gridSize.Z * gridSize.Y;
        int terrainHeight = maxTerrainHeight - minTerrainHeight;
        int waterLevel = minTerrainHeight + (int)Math.Floor(terrainHeight * waterPercentage);

        var world = new ushort[VoxelCount * 4];

        // Generate Height Map
        var map = DiamondSquare.Generate(gridSize.X, gridSize.Z, DiamondSquare.StartIterForRegionSize(gridSize.X, gridSize.Z, 128));
        DiamondSquare.Standardize(map, gridSize.X, gridSize.Z, .175f);

        // Generate Landmass and Water
        for (var i = 0; i < VoxelCount; i++)
        {
            var x = i % gridSize.X;
            var y = i / gridSize.X % gridSize.Y;
            var z = i / (gridSize.X * gridSize.Y);
            var idx = i * 4;

            var surfaceLevel = (int)(map[x, z] * terrainHeight) + minTerrainHeight;

            if (y <= surfaceLevel)
            {
                world[idx] = DIRT_IDX;
            }
            else if (y <= waterLevel)
            {
                world[idx] = WATER_IDX;
            }
            else
            {
                world[idx] = AIR_IDX;
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
            var x = i % gridSize.X;
            var y = (i / gridSize.X) % gridSize.Y;
            var z = i / (gridSize.X * gridSize.Y);
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