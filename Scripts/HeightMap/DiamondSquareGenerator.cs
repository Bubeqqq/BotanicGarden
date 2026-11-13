using Godot;

// 2D preview of the diamond-square heightmap (Scenes/HeightMapGeneration.tscn).
// The algorithm itself lives in DiamondSquare.cs.
public partial class DiamondSquareGenerator : Sprite2D
{
    [Export] public int Width = (1 << 8) + 1;
    [Export] public int Height = (1 << 8) + 1;
    [Export] public int StartIter = 2;
    [Export] public float StandardizeMulti = .18f;


    private ImageTexture CreateTexture(float[,] arr)
    {
        Image img = Image.CreateEmpty(Width, Height, false, Image.Format.Rgba8);

        for (int y = 0; y < Height; y++)
        {
            for (int x = 0; x < Width; x++)
            {
                float v = arr[x, y];
                img.SetPixel(x, y, new Color(v, v, v));
            }
        }

        return ImageTexture.CreateFromImage(img);
    }

    private static readonly (float Low, float High, Color LowColor, Color HighColor)[] ColorBands =
    {
        (0.00f, 0.40f, Color.Color8( 32,  21,  89), Color.Color8( 71, 185, 237)), // ocean
        (0.40f, 0.42f, Color.Color8(230, 247, 255), Color.Color8(230, 247, 255)), // shore
        (0.42f, 0.57f, Color.Color8( 57, 191,  73), Color.Color8(217, 217,  30)), // low-lands
        (0.57f, 0.65f, Color.Color8(217, 217,  30), Color.Color8(201, 151,  24)), // mid-lands
        (0.65f, 0.70f, Color.Color8(201, 151,  24), Color.Color8( 80,  80,  80)), // high-lands
        (0.70f, 0.81f, Color.Color8( 80,  80,  80), Color.Color8(150, 150, 150)), // mountains
        (0.81f, 1.01f, Color.Color8(180, 180, 180), Color.Color8(255, 255, 255)), // peaks
    };

    private static Color HeightToColor(float v)
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

    public override void _Ready()
    {
        float[,] arr = DiamondSquare.Generate(Width, Height, StartIter);
        DiamondSquare.Standardize(arr, Width, Height, StandardizeMulti);
        Texture = CreateColorTexture(arr);
        // Texture = CreateTexture(arr);
        Centered = false;
    }
}
