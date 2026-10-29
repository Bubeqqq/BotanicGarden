using System;

namespace MyGame.Utils
{
    public static class ArrayExtensions
    {
        public static float Sum(this float[,] a) => a.Sum(a.GetLength(0), a.GetLength(1));

        public static float Sum(this float[,] a, int width, int height)
        {
            CheckBounds(a, width, height);
            float s = 0f;
            for (int y = 0; y < height; y++)
                for (int x = 0; x < width; x++) s += a[x, y];
            return s;
        }

        public static float Mean(this float[,] a) => a.Mean(a.GetLength(0), a.GetLength(1));

        public static float Mean(this float[,] a, int width, int height) => a.Sum(width, height) / (width * height);

        public static float Min(this float[,] a) => a.Min(a.GetLength(0), a.GetLength(1));

        public static float Min(this float[,] a, int width, int height)
        {
            CheckBounds(a, width, height);
            float m = float.MaxValue;
            for (int y = 0; y < height; y++)
                for (int x = 0; x < width; x++) if (a[x, y] < m) m = a[x, y];
            return m;
        }

        public static float Max(this float[,] a) => a.Max(a.GetLength(0), a.GetLength(1));

        public static float Max(this float[,] a, int width, int height)
        {
            CheckBounds(a, width, height);
            float m = float.MinValue;
            for (int y = 0; y < height; y++)
                for (int x = 0; x < width; x++) if (a[x, y] > m) m = a[x, y];
            return m;
        }

        public static float Std(this float[,] a) => a.Std(a.GetLength(0), a.GetLength(1));

        public static float Std(this float[,] a, int width, int height)
        {
            float mean = a.Mean(width, height);
            double acc = 0;
            for (int y = 0; y < height; y++)
                for (int x = 0; x < width; x++) { double d = a[x, y] - mean; acc += d * d; }
            return (float)Math.Sqrt(acc / (width * height - 1));
        }

        public static float[] MeanAxis0(this float[,] a) => a.MeanAxis0(a.GetLength(0), a.GetLength(1));

        public static float[] MeanAxis0(this float[,] a, int width, int height)
        {
            CheckBounds(a, width, height);
            var result = new float[height];
            for (int y = 0; y < height; y++)
            {
                float s = 0f;
                for (int x = 0; x < width; x++) s += a[x, y];
                result[y] = s / width;
            }
            return result;
        }

        public static void Clip(this float[,] a, float min, float max) => a.Clip(min, max, a.GetLength(0), a.GetLength(1));

        public static void Clip(this float[,] a, float min, float max, int width, int height)
        {
            CheckBounds(a, width, height);
            for (int y = 0; y < height; y++)
            {
                for (int x = 0; x < width; x++)
                {
                    a[x, y] = Math.Min(max, Math.Max(min, a[x, y]));
                }
            }
        }

        private static void CheckBounds(float[,] a, int width, int height)
        {
            if (width <= 0 || width > a.GetLength(0)) throw new ArgumentOutOfRangeException(nameof(width));
            if (height <= 0 || height > a.GetLength(1)) throw new ArgumentOutOfRangeException(nameof(height));
        }
    }
}
