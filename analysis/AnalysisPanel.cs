using Godot;
using System.Collections.Generic;
using System.Linq;
using BotanicGarden.Player;
using BotanicGarden.Simulation;

namespace BotanicGarden.UI;

public partial class AnalysisPanel : PanelContainer
{
	[Export] public WorldRender WorldRender;
	[Export] public CameraMovement Camera;
	[Export] public Label SummaryLabel;
	[Export] public Button ModeButton;
	[Export] public VBoxContainer SpeciesList;
	[Export] public PopulationChart Chart;
	[Export] public MaturityHistogram Histogram;
	[Export] public OptionButton GrowthWindowOption;

	private static readonly int[] GrowthWindowPresets = [1, 3, 5, 10, 20, 50];
	private int _growthWindowSamples = 5;

	[Export] public string AuxJsonPath = "res://voxel_data/voxel_editor_aux.json";
	[Export] public int MaxHistorySamples = 90;

	private readonly List<GardenAnalysisSnapshot> _history = [];
	private Dictionary<uint, SpeciesVisualInfo> _metadata = [];
	private bool _showVoxels = false;

	public override void _Ready()
	{
		Visible = false;
		_metadata = SpeciesMetadataLoader.Load("res://voxel_data/voxel_data.json", AuxJsonPath);
		if (ModeButton != null)
			ModeButton.Pressed += OnToggleModePressed;

		if (WorldRender != null)
			WorldRender.AnalysisUpdated += OnAnalysisUpdated;

		if (GrowthWindowOption != null)
		{
			GrowthWindowOption.Clear();
			for (int i = 0; i < GrowthWindowPresets.Length; i++)
			{
				int samples = GrowthWindowPresets[i];
				GrowthWindowOption.AddItem($"Growth: {samples} samples ({samples * 20} steps)", samples);
				if (samples == _growthWindowSamples)
					GrowthWindowOption.Select(i);
			}

			GrowthWindowOption.ItemSelected += OnGrowthWindowSelected;
		}
	}
	private void OnGrowthWindowSelected(long index)
	{
		_growthWindowSamples = GrowthWindowOption.GetItemId((int)index);
		RefreshUi();
	}
	public override void _ExitTree()
	{
		if (WorldRender != null)
			WorldRender.AnalysisUpdated -= OnAnalysisUpdated;
		if (ModeButton != null)
			ModeButton.Pressed -= OnToggleModePressed;
		if (GrowthWindowOption != null)
			GrowthWindowOption.ItemSelected -= OnGrowthWindowSelected;
	}

	public override void _Input(InputEvent @event)
	{
		if (@event.IsActionPressed("toggle_analysis"))
		{
			SetPanelOpen(!Visible);
			GetViewport().SetInputAsHandled();
		}
	}

	private void SetPanelOpen(bool open)
	{
		Visible = open;

		if (Camera != null)
			Camera.IsUiOpen = open;

		Input.SetMouseMode(open ? Input.MouseModeEnum.Visible : Input.MouseModeEnum.Captured);

		if (open)
			RefreshUi();
	}

	private void OnToggleModePressed()
	{
		_showVoxels = !_showVoxels;
		if (ModeButton != null)
			ModeButton.Text = _showVoxels ? "Mode: Voxel Count" : "Mode: Plant Count";

		if (Chart != null)
			Chart.ShowVoxelsInsteadOfPlants = _showVoxels;

		RefreshUi();
	}

	private void OnAnalysisUpdated(GardenAnalysisSnapshot snapshot)
	{
		_history.Add(snapshot);
		if (_history.Count > MaxHistorySamples)
			_history.RemoveAt(0);

		if (Visible)
			RefreshUi();
	}

	private void RefreshUi()
	{
		if (_history.Count == 0)
		{
			if (SummaryLabel != null)
				SummaryLabel.Text = "No Data Analysis...";
			return;
		}

		var latest = _history[^1];

		if (SummaryLabel != null)
		{
			SummaryLabel.Text =
				$"Plants: {latest.TotalPlants:N0}  |  " +
				$"Plant Voxels: {latest.TotalPlantVoxels:N0}  |  " +
				$"Species: {latest.BySpecies.Count}  |  " +
				$"FPS: {latest.Fps} ({latest.SimStepsPerSec:0.0} sim/s)";
		}

		RebuildSpeciesSummary(latest);
		Chart?.SetData(_history, _metadata);
		Histogram?.SetData(latest, _metadata);
	}
	private double CalculateGrowthRatePerPlant(uint speciesId, int windowSamples = 5)
	{
		if (_history.Count < 2) return 0.0;

		var latest = _history[^1];
		int oldIdx = System.Math.Max(0, _history.Count - 1 - windowSamples);
		var oldest = _history[oldIdx];

		double dt = latest.SimTimeSeconds - oldest.SimTimeSeconds;
		if (dt <= 0.0001) return 0.0;

		latest.BySpecies.TryGetValue(speciesId, out var latestStats);
		oldest.BySpecies.TryGetValue(speciesId, out var oldestStats);

		long deltaVoxels = latestStats.VoxelCount - oldestStats.VoxelCount;
		double avgPlants = (latestStats.PlantCount + oldestStats.PlantCount) * 0.5;

		return avgPlants > 0.0 ? (deltaVoxels / dt) / avgPlants : 0.0;
	}
	private void RebuildSpeciesSummary(GardenAnalysisSnapshot latest)
	{
		if (SpeciesList == null) return;

		foreach (Node child in SpeciesList.GetChildren())
			child.QueueFree();

		var ordered = latest.BySpecies.Values
			.OrderByDescending(s => _showVoxels ? s.VoxelCount : s.PlantCount);

		long totalDenominator = _showVoxels
			? System.Math.Max(1, latest.TotalPlantVoxels)
			: System.Math.Max(1, latest.TotalPlants);

		foreach (var stats in ordered)
		{
			var info = SpeciesMetadataLoader.Resolve(_metadata, stats.SpeciesId);
			long metric = _showVoxels ? stats.VoxelCount : stats.PlantCount;
			double percent = 100.0 * metric / totalDenominator;

			var row = new HBoxContainer { SizeFlagsHorizontal = SizeFlags.ExpandFill };
			row.AddThemeConstantOverride("separation", 10);

			var swatch = new ColorRect
			{
				Color = info.Color,
				CustomMinimumSize = new Vector2(14, 14),
				SizeFlagsVertical = SizeFlags.ShrinkCenter
			};

			var nameLabel = new Label
			{
				Text = info.Name,
				CustomMinimumSize = new Vector2(110, 0)
			};

			var bar = new ProgressBar
			{
				MinValue = 0,
				MaxValue = 100,
				Value = percent,
				ShowPercentage = false,
				CustomMinimumSize = new Vector2(150, 14),
				SizeFlagsHorizontal = SizeFlags.ExpandFill,
				SizeFlagsVertical = SizeFlags.ShrinkCenter
			};

			var fillStyle = new StyleBoxFlat { BgColor = info.Color };
			bar.AddThemeStyleboxOverride("fill", fillStyle);

			double growth = CalculateGrowthRatePerPlant(stats.SpeciesId, _growthWindowSamples);
			string sign = growth >= 0 ? "+" : "";

			var countLabel = new Label
			{
				Text = $"{stats.PlantCount} plants [{percent:0.0}%] | {stats.VoxelCount:N0} voxels (avg. {stats.AverageSize:0.0}) | Growth: {sign}{growth:0.00} vox/s",
				HorizontalAlignment = HorizontalAlignment.Right
			};

			row.AddChild(swatch);
			row.AddChild(nameLabel);
			row.AddChild(bar);
			row.AddChild(countLabel);
			SpeciesList.AddChild(row);
		}
	}
}
