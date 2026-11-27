using Godot;
using System;
using BotanicGarden.Common;

namespace BotanicGarden.WorldGen;

public static class WorldGenerator
{
    private const ushort WATER_IDX = 8193;
    private const ushort DIRT_IDX = 6144;
    private const ushort STONE_IDX = 2048;
    private const ushort WOOD_IDX = 2049;
    private const ushort AIR_IDX = 0;
    private const ushort IGNORE_IDX = ushort.MaxValue;

    private static int CoordsToNo(Vector3I coords, Vector3I size)
    {
        var index = coords.X + (coords.Y  + coords.Z * size.Y) * size.X;
        return index;
    }

    private static Vector3I NoToCoords(int index, Vector3I gridSize)
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

    private static void CopyBlock(ushort[]toTable, int toNumber, ushort[] fromTable, int fromNumber)
    {
        toTable[4 * toNumber    ] = fromTable[4 * fromNumber    ];
        toTable[4 * toNumber + 1] = fromTable[4 * fromNumber + 1];
        toTable[4 * toNumber + 2] = fromTable[4 * fromNumber + 2];
        toTable[4 * toNumber + 3] = fromTable[4 * fromNumber + 3];
    }

    private static bool PasteModel(
        ushort[] world,
        Vector3I gridSize,
        Vector3I position,
        Model model,
        ushort[] allowedSpawnBlockTypes,
        ushort[] allowedReplaceBlockTypes,
        ushort[] ignoreCopyBlockTypes
    )
    {
        ignoreCopyBlockTypes = [..ignoreCopyBlockTypes, IGNORE_IDX];
        ushort spawnBlock = world[4 * CoordsToNo(position-model.origin, gridSize)];
        if (!BlockInBlockList(spawnBlock, allowedSpawnBlockTypes)) return false;

        // todo: implement

        var minWorld = position;
        var maxWorld = gridSize - position;

        var minModel = model.origin;
        var maxModel = model.size - model.origin;

        var min = -new Vector3I(
            Math.Min(minWorld.X, minModel.X),
            Math.Min(minWorld.Y, minModel.Y),
            Math.Min(minWorld.Z, minModel.Z)
        );
        var max = new Vector3I(
            Math.Min(maxWorld.X, maxModel.X),
            Math.Min(maxWorld.Y, maxModel.Y),
            Math.Min(maxWorld.Z, maxModel.Z)
        );

        for (int x = min.X; x < max.X; ++x)
        {
            for (int y = min.Y; y < max.Y; ++y)
            {
                for (int z = min.Z; z < max.Z; ++z)
                {
                    var p = new Vector3I(x, y, z);
                    Vector3I coordsWorld = p + position;
                    Vector3I coordsModel = p + model.origin;
                    int noWorld = CoordsToNo(coordsWorld, gridSize);
                    int noModel = CoordsToNo(coordsModel, model.size);

                    if (!BlockInBlockList(world[4 * noWorld], allowedReplaceBlockTypes)) continue;
                    if (BlockInBlockList(model.data[4 * noModel], ignoreCopyBlockTypes)) continue;
                    CopyBlock(world, noWorld, model.data, noModel);
                }
            }
        }

        return true;
    }

    public static void ScatterModel(
        ushort[] world,
        Vector3I gridSize,
        Model model,
        int count,
        int verticalOffset,
        int[,] heightMap,
        ushort[] allowedSpawnBlockTypes,
        ushort[] allowedReplaceBlockTypes,
        ushort[] ignoreCopyBlockTypes
    )
    {
        var random = new Random();
        for (int i = 0; i < count; ++i)
        {
            int x = random.Next() % heightMap.GetLength(0);
            int z = random.Next() % heightMap.GetLength(1);
            var position = new Vector3I(x, heightMap[x, z] + verticalOffset, z);
            if (!PasteModel(world, gridSize, position, model, allowedSpawnBlockTypes, allowedReplaceBlockTypes, ignoreCopyBlockTypes)) --i;
        }
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
        int[,] heightMap = map.Convert(x => (int)((x * terrainHeight) + minTerrainHeight));

        // Generate Landmass and Water
        for (var i = 0; i < VoxelCount; i++)
        {
            var x = i % gridSize.X;
            var y = i / gridSize.X % gridSize.Y;
            var z = i / (gridSize.X * gridSize.Y);
            var idx = i * 4;

            if (y <= heightMap[x, z])
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
        // Todo: fix
        var fencePicketSize = new Vector3I(1, 20, 5);
        var fencePicketData = new ushort[4 * (int)fencePicketSize.Length()];
        for (int i = 0; i < (int)fencePicketSize.Length(); ++i) fencePicketData[4*i] = WOOD_IDX;
        var fencePicket = new Model(
            new Vector3I(1, 5, 2),
            fencePicketSize,
            fencePicketData
        );
        var startPosition = new Vector2I(2, 2);
        var offset = new Vector2I(7, 0);
        for (int i = 0; i < 5; ++i)
        {
            Vector2I xz = startPosition + offset * i;
            var position = new Vector3I(xz.X, heightMap[xz.X, xz.Y]+1, xz.Y);
            GD.PrintS(position);
            PasteModel(world, gridSize, position, fencePicket, [AIR_IDX], [AIR_IDX], []);
        }

        // Generate Lampposts
        // Todo: implement

        // Scatter rocks
        // Todo: add new models
        var rock_test = new Model(
            new Vector3I(1, 1, 1),
            new Vector3I(3, 3, 3),
            [
                AIR_IDX  ,0,0,0, STONE_IDX,0,0,0, STONE_IDX,0,0,0,
                STONE_IDX,0,0,0, AIR_IDX  ,0,0,0, STONE_IDX,0,0,0,
                STONE_IDX,0,0,0, STONE_IDX,0,0,0, STONE_IDX,0,0,0,

                AIR_IDX  ,0,0,0, STONE_IDX,0,0,0, STONE_IDX,0,0,0,
                AIR_IDX  ,0,0,0, STONE_IDX,0,0,0, STONE_IDX,0,0,0,
                STONE_IDX,0,0,0, AIR_IDX  ,0,0,0, AIR_IDX  ,0,0,0,

                STONE_IDX,0,0,0, STONE_IDX,0,0,0, AIR_IDX  ,0,0,0,
                STONE_IDX,0,0,0, STONE_IDX,0,0,0, STONE_IDX,0,0,0,
                AIR_IDX  ,0,0,0, STONE_IDX,0,0,0, STONE_IDX,0,0,0
            ]
        );
        // PasteModel(world, gridSize, new Vector3I(128, 64, 128), rock_test, [AIR_IDX, DIRT_IDX, WATER_IDX], [AIR_IDX, DIRT_IDX, WATER_IDX], []);
        ScatterModel(world, gridSize, rock_test, 20, 1, heightMap, [AIR_IDX, DIRT_IDX, WATER_IDX], [AIR_IDX, DIRT_IDX, WATER_IDX], []);

        // var random_size = new Vector3I(20, 20, 20);
        // var random_len = random_size.X * random_size.Y * random_size.Z;
        // var random_array = new ushort[random_len];
        // var random = new Random();
        // for (int i = 0; i < random_len; ++i) random_array[i] = (random.Next() % 2 == 0) ? STONE_IDX : AIR_IDX;
        // var rock_test2 = new Model(
        //     random_size / 2,
        //     random_size,
        //     random_array
        // );
        // // GD.PrintS(rock_test2);
        // PasteModel(world, gridSize, new Vector3I(128, 64, 128), rock_test2, [AIR_IDX, DIRT_IDX, WATER_IDX], [AIR_IDX, DIRT_IDX, WATER_IDX]);

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