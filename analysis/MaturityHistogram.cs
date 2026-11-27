using Godot;
using System;
using System.Collections.Generic;
using System.Linq;
using BotanicGarden.Simulation;

namespace BotanicGarden.UI;

public partial class MaturityHistogram : Control
{
	private static readonly string[] StageLabels =
	[
		"Very Small (1-4)",
		"Small (5-15)",
		"Medium (16-45)",
        "Big (46+)"
	];

	private GardenAnalysisSnapshot _snapshot;
	private Dictionary<uint, SpeciesVisualInfo> _metadata = [];

	public void SetData(GardenAnalysisSnapshot snapshot, Dictionary<uint, SpeciesVisualInfo> metadata)
	{
		_snapshot = snapshot;
		_metadata = metadata;
		QueueRedraw();
	}

	public override void _Draw()
	{
		DrawRect(new Rect2(Vector2.Zero, Size), new Color(0.08f, 0.1f, 0.13f, 0.9f), true);

		var font = ThemeDB.FallbackFont;
		const int fontSize = 12;

		if (_snapshot == null || _snapshot.TotalPlants == 0)
		{
			DrawString(font, new Vector2(16, Size.Y * 0.5f),
				"Brak roślin w symulacji.", HorizontalAlignment.Left, -1, fontSize, Colors.Gray);
			return;
		}

		DrawEcosystemHeader(font, fontSize);

		const float padLeft = 24f;
		const float padRight = 24f;
		const float padTop = 52f;
		const float padBottom = 28f;

		float plotW = Size.X - padLeft - padRight;
		float plotH = Size.Y - padTop - padBottom;
		if (plotW <= 20 || plotH <= 20) return;

		var stageTotals = new int[4];
		foreach (var stats in _snapshot.BySpecies.Values)
		{
			for (int s = 0; s < 4; s++)
				stageTotals[s] += stats.StageCounts[s];
		}

		int maxStageTotal = Math.Max(1, stageTotals.Max());
		float slotW = plotW / 4f;
		float barW = slotW * 0.55f;

		var orderedSpecies = _snapshot.BySpecies.Values.OrderBy(s => s.SpeciesId).ToList();

		for (int s = 0; s < 4; s++)
		{
			float barX = padLeft + s * slotW + (slotW - barW) * 0.5f;
			float currentBottom = padTop + plotH;

			foreach (var stats in orderedSpecies)
			{
				int count = stats.StageCounts[s];
				if (count == 0) continue;

				float segH = plotH * ((float)count / maxStageTotal);
				var info = SpeciesMetadataLoader.Resolve(_metadata, stats.SpeciesId);

				DrawRect(new Rect2(barX, currentBottom - segH, barW, segH), info.Color, true);
				currentBottom -= segH;
			}

			if (stageTotals[s] > 0)
			{
				DrawString(font, new Vector2(barX, currentBottom - 5),
					stageTotals[s].ToString("N0"),
					HorizontalAlignment.Center, barW, fontSize, Colors.White);
			}

			DrawString(font, new Vector2(padLeft + s * slotW, Size.Y - 8),
				StageLabels[s],
				HorizontalAlignment.Center, slotW, fontSize, Colors.LightGray);
		}

		DrawLine(
			new Vector2(padLeft, padTop + plotH),
			new Vector2(padLeft + plotW, padTop + plotH),
			new Color(1, 1, 1, 0.35f), 1.5f);
	}

	private void DrawEcosystemHeader(Font font, int fontSize)
	{
	var champInfo = SpeciesMetadataLoader.Resolve(_metadata, _snapshot.LargestPlantSpeciesId);
	string champText = $"Biggest specimen: {champInfo.Name} ({_snapshot.LargestPlantVoxels:N0} voxels)";

	DrawString(font, new Vector2(16, 22),
		champText, HorizontalAlignment.Left, -1, fontSize + 1, champInfo.Color);
	}
}
