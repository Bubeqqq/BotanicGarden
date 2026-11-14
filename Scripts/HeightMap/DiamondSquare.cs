using Godot;
using MyGame.Utils;
using System;

/*
Diamond-square heightmap generation, independent of any scene node.
Used by WorldRender (initial terrain) and DiamondSquareGenerator (2D preview).
*/
public static class DiamondSquare
{
    /*
    Params:
        width, height
            requested map size; the returned array is a square of side 2^n + 1 >= max(width, height)
        startIter
            has to be a non-negative integer
            controls how zoomed out the terrain feels, higher value - bigger zoom
        multi
            scales the noise by a factor; basically useless since we standardize the values later
        seed
            optional seed for reproducible maps; random when null

    Returns:
        array with size at least [width, height]

    Other Notes:
        Generating noise map with shape far from a square, with `startIter` higher than 0 can be optimized
    */
    public static float[,] Generate(int width, int height, int startIter = 0, float multi = 1f, ulong? seed = null)
    {
        int iter = Iterations(width, height);
        int size = (1 << iter) + 1;

        if (startIter < 0 || startIter > iter)
            throw new ArgumentOutOfRangeException(nameof(startIter), $"startIter musi być w zakresie [0, {iter}]");

        var random = new RandomNumberGenerator();
        if (seed.HasValue)
            random.Seed = seed.Value;

        float[,] arr = new float[size, size];

        // Init Corners
        int startIncrement = 1 << (iter - startIter);
        for (int y = 0; y < size; y += startIncrement)
        {
            for (int x = 0; x < size; x += startIncrement)
            {
                arr[x, y] = random.RandfRange(-multi, multi);
            }
        }

        // Main Loop
        for (int i = startIter; i < iter; i++)
        {
            int increment = 1 << (iter-i);
            int increment2 = increment / 2;

            // Stage 1
            for (int l = 0; l < size-1; l += increment)
            {
                for (int t = 0; t < size-1; t += increment)
                {
                    int r = l + increment;
                    int b = t + increment;

                    int x = (l + r) / 2;
                    int y = (t + b) / 2;

                    float a = (arr[l, t] + arr[r, t] + arr[l, b] + arr[r, b]) / 4f;
                    float m = random.RandfRange(-multi, multi);
                    arr[x, y] = a + m;
                }
            }

            // Stage 2
            for (int x = 0; x < size; x += increment2)
            {
                for (int y = 0; y < size; y += increment2)
                {
                    if ((x / increment2 + y / increment2) % 2 == 0) continue;

                    int count = 4;

                    float lv, rv, tv, bv;
                    lv = rv = tv = bv = 0f;

                    if (x - increment2 >= 0)
                    {
                        lv = arr[x - increment2, y];
                    } else {
                        count -= 1;
                    }

                    if (x + increment2 < size)
                    {
                        rv = arr[x + increment2, y];
                    } else {
                        count -= 1;
                    }

                    if (y - increment2 >= 0)
                    {
                        tv = arr[x, y - increment2];
                    } else {
                        count -= 1;
                    }

                    if (y + increment2 < size)
                    {
                        bv = arr[x, y + increment2];
                    } else {
                        count -= 1;
                    }

                    float a = (lv + rv + tv + bv) / count;
                    float m = random.RandfRange(-multi, multi);
                    arr[x, y] = a + m;
                }
            }
            multi /= 2;
        }

        return arr;
    }

    // Number of subdivision steps for a map of this size (map side = 2^iter + 1).
    private static int Iterations(int width, int height)
    {
        return (int) Math.Ceiling(Math.Log2(Math.Max(Math.Max(width, height), 2) - 1d));
    }

    /*
    Returns the startIter for which the initial random corners are `regionSize` apart,
    so every regionSize x regionSize block of the map behaves like a separate full map.
    regionSize must be a power of two; maps smaller than one region get 0.
    */
    public static int StartIterForRegionSize(int width, int height, int regionSize = 256)
    {
        int regionIter = (int) Math.Round(Math.Log2(regionSize));
        if (1 << regionIter != regionSize)
            throw new ArgumentException($"regionSize musi być potęgą dwójki, podano {regionSize}", nameof(regionSize));

        return Math.Max(0, Iterations(width, height) - regionIter);
    }

    // Standardizes the [width, height] region to mean 0.5, scaled by multi/std, clipped to [0, 1].
    public static void Standardize(float[,] arr, int width, int height, float multi = 1f)
    {
        float mean = arr.Mean(width, height);
        float std = arr.Std(width, height);

        arr.Subtract(mean, width, height);
        arr.Multiply(multi/std, width, height);
        arr.Add(0.5f, width, height);
        arr.Clip(0f, 1f, width, height);
    }

    // Rescales the [width, height] region linearly to [0, 1].
    public static void StandardizeMinMax(float[,] arr, int width, int height)
    {
        float min = arr.Min(width, height);
        float max = arr.Max(width, height);

        arr.Subtract(min, width, height);
        arr.Multiply(1f/(max-min), width, height);
        arr.Clip(0f, 1f, width, height);
    }
}
