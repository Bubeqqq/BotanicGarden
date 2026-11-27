using System.Collections.Generic;

namespace BotanicGarden.Simulation;

public readonly record struct SpeciesStats(
    uint SpeciesId,
    int PlantCount,
    long VoxelCount,
    int[] StageCounts)
{
    public float AverageSize => PlantCount > 0 ? (float)VoxelCount / PlantCount : 0f;
}

public sealed class GardenAnalysisSnapshot
{
    public double SimTimeSeconds { get; init; }
    public int TotalPlants { get; init; }
    public long TotalPlantVoxels { get; init; }
    public int Fps { get; init; }
    public double SimStepsPerSec { get; init; }
    public uint LargestPlantSpeciesId { get; init; }
    public uint LargestPlantVoxels { get; init; }
    public Dictionary<uint, SpeciesStats> BySpecies { get; init; } = [];
}