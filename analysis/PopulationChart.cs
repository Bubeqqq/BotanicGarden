using Godot;
using System;
using System.Collections.Generic;
using System.Linq;
using BotanicGarden.Simulation;

namespace BotanicGarden.UI;

public partial class PopulationChart : Control
{
	public bool ShowVoxelsInsteadOfPlants { get; set; } = false;

	private IReadOnlyList<GardenAnalysisSnapshot> _history = Array.Empty<GardenAnalysisSnapshot>();
	private Dictionary<uint, SpeciesVisualInfo> _metadata = [];

	public void SetData(
		IReadOnlyList<GardenAnalysisSnapshot> history,
		Dictionary<uint, SpeciesVisualInfo> metadata)
	{
		_history = history;
		_metadata = metadata;
		QueueRedraw();
	}

	public override void _Draw()
	{
		var rect = new Rect2(Vector2.Zero, Size);
		DrawRect(rect, new Color(0.08f, 0.1f, 0.13f, 0.9f), true);

		const float padLeft = 58f;
		const float padRight = 16f;
		const float padTop = 16f;
		const float padBottom = 26f;

		float plotW = Size.X - padLeft - padRight;
		float plotH = Size.Y - padTop - padBottom;
		if (plotW <= 10 || plotH <= 10) return;

		var font = ThemeDB.FallbackFont;
		const int fontSize = 12;

		if (_history.Count < 2)
		{
			DrawString(font, new Vector2(padLeft + 10, padTop + plotH * 0.5f),
				"Zbieranie próbek symulacji...", HorizontalAlignment.Left, -1, fontSize, Colors.Gray);
			return;
		}

		long maxVal = 1;
		var allSpecies = new HashSet<uint>();
		foreach (var snap in _history)
		{
			foreach (var (id, stats) in snap.BySpecies)
			{
				allSpecies.Add(id);
				long v = ShowVoxelsInsteadOfPlants ? stats.VoxelCount : stats.PlantCount;
				if (v > maxVal) maxVal = v;
			}
		}

		var gridColor = new Color(1, 1, 1, 0.12f);
		for (int i = 0; i <= 4; i++)
		{
			float t = i / 4f;
			float y = padTop + plotH * (1f - t);
			DrawLine(new Vector2(padLeft, y), new Vector2(padLeft + plotW, y), gridColor, 1f);

			long labelVal = (long)Math.Round(maxVal * t);
			DrawString(font, new Vector2(4, y + 4), labelVal.ToString("N0"),
				HorizontalAlignment.Left, padLeft - 8, fontSize, Colors.LightGray);
		}

		var axisColor = new Color(1, 1, 1, 0.4f);
		DrawLine(new Vector2(padLeft, padTop), new Vector2(padLeft, padTop + plotH), axisColor, 1.5f);
		DrawLine(new Vector2(padLeft, padTop + plotH), new Vector2(padLeft + plotW, padTop + plotH), axisColor, 1.5f);

		int n = _history.Count;
		var points = new Vector2[n];

		foreach (uint speciesId in allSpecies.OrderBy(x => x))
		{
			var info = SpeciesMetadataLoader.Resolve(_metadata, speciesId);

			for (int i = 0; i < n; i++)
			{
				float x = padLeft + (plotW * i / (n - 1));
				long val = 0;
				if (_history[i].BySpecies.TryGetValue(speciesId, out var stats))
					val = ShowVoxelsInsteadOfPlants ? stats.VoxelCount : stats.PlantCount;

				float y = padTop + plotH * (1f - (float)val / maxVal);
				points[i] = new Vector2(x, y);
			}

			DrawPolyline(points, info.Color, 2.5f, antialiased: true);
		}

		double tStart = _history[0].SimTimeSeconds;
		double tEnd = _history[^1].SimTimeSeconds;
		DrawString(font, new Vector2(padLeft, Size.Y - 6), $"{tStart:0.0}s",
			HorizontalAlignment.Left, -1, fontSize, Colors.LightGray);
		DrawString(font, new Vector2(padLeft + plotW - 45, Size.Y - 6), $"{tEnd:0.0}s",
			HorizontalAlignment.Left, -1, fontSize, Colors.LightGray);
	}
}
