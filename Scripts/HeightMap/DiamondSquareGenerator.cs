using Godot;
using MyGame.Utils;
using System;
using System.Diagnostics;
using System.Drawing;

public partial class DiamondSquareGenerator : Sprite2D
{
    [Export] public int Width = 257;
    [Export] public int Height = 257;


    private ImageTexture CreateTexture(float[,] arr)
    {
        Image img = Image.CreateEmpty(Width, Height, false, Image.Format.Rgba8);
        
        for (int y = 0; y < Height; y++)
        {
            for (int x = 0; x < Width; x++)
            {
                float v = arr[x, y];
                img.SetPixel(x, y, new Godot.Color(v, v, v));
            }
        }

        return ImageTexture.CreateFromImage(img);
    }

    private static readonly (float Low, float High, Godot.Color LowColor, Godot.Color HighColor)[] ColorBands =
    {
        (0.00f, 0.40f, Godot.Color.Color8( 32,  21,  89), Godot.Color.Color8( 71, 185, 237)), // ocean
        (0.40f, 0.42f, Godot.Color.Color8(230, 247, 255), Godot.Color.Color8(230, 247, 255)), // shore
        (0.42f, 0.57f, Godot.Color.Color8( 57, 191,  73), Godot.Color.Color8(217, 217,  30)), // low-lands
        (0.57f, 0.65f, Godot.Color.Color8(217, 217,  30), Godot.Color.Color8(201, 151,  24)), // mid-lands
        (0.65f, 0.70f, Godot.Color.Color8(201, 151,  24), Godot.Color.Color8( 80,  80,  80)), // high-lands
        (0.70f, 0.81f, Godot.Color.Color8( 80,  80,  80), Godot.Color.Color8(150, 150, 150)), // mountains
        (0.81f, 1.01f, Godot.Color.Color8(180, 180, 180), Godot.Color.Color8(255, 255, 255)), // peaks
    };

    private static Godot.Color HeightToColor(float v)
    {
        foreach (var band in ColorBands)
        {
            if (v >= band.Low && v < band.High)
            {
                float t = (v - band.Low) / (band.High - band.Low);
                return band.LowColor.Lerp(band.HighColor, t);
            }
        }

        return v < ColorBands[0].Low ? ColorBands[0].LowColor : ColorBands[^1].HighColor;
    }

    private ImageTexture CreateColorTexture(float[,] arr)
    {
        Image img = Image.CreateEmpty(Width, Height, false, Image.Format.Rgba8);

        for (int y = 0; y < Height; y++)
        {
            for (int x = 0; x < Width; x++)
            {
                img.SetPixel(x, y, HeightToColor(arr[x, y]));
            }
        }

        return ImageTexture.CreateFromImage(img);
    }

    private void Standardize(float[,] arr, float multi = 1f)
    {
        float mean = arr.Mean(Width, Height);
        float std = arr.Std(Width, Height);

        for (int y = 0; y < Height; y++)
        {
            for (int x = 0; x < Width; x++)
            {
                arr[x, y] -= mean;
                arr[x, y] *= multi / std;
                arr[x, y] += 0.5f;
            }
        }
    }

    private float[,] Generate(float multi = 1f)
    {
        int iter = (int) Math.Ceiling(Math.Log2(Math.Max(Width, Height)-1d));
        int size = (int) (1 << iter) + 1;

        var random = new RandomNumberGenerator();
        // random.Seed = 0;

        float[,] arr = new float[size, size];

        // Init Corners
        arr[     0,      0] = multi * random.RandfRange(-1f, 1f);
        arr[     0, size-1] = multi * random.RandfRange(-1f, 1f);
        arr[size-1,      0] = multi * random.RandfRange(-1f, 1f);
        arr[size-1, size-1] = multi * random.RandfRange(-1f, 1f);

        // Main Loop
        for (int i = 0; i < iter; i++)
        {
            int increment = (int) 1 << (iter-i);
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
                    float m = multi * random.RandfRange(-1f, 1f);
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
                    float m = multi * random.RandfRange(-1f, 1f);
                    arr[x, y] = a + m;
                }
            }
            multi /= 2;
        }

        return arr;
    }
    public override void _Ready()
    {
        float[,] arr = Generate(1);
        Standardize(arr, .2f);
        arr.Clip(0f, 1f, Width, Height);
        Texture = CreateColorTexture(arr);
        // Texture = CreateTexture(arr);
        Centered = false;
    }
}
