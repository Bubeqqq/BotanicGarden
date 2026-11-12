using Godot;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;
using BotanicGarden.Scripts.Render;

public class VoxelAuxData
{
	[JsonPropertyName("voxel_names")]
	public Dictionary<string, string> VoxelNames { get; set; } = new();

	[JsonPropertyName("groups")]
	public Dictionary<string, List<ushort>> Groups { get; set; } = new();

	[JsonPropertyName("type_names")]
	public Dictionary<string, string> TypeNames { get; set; } = new();
}

public partial class BlockSelectorUI : Control
{
	[Export] public string AuxJsonPath = "VoxelData/VoxelEditor_Aux.json";
	[Export] public CameraMovement CameraController;

	[Export] public ItemList TypesList;
	[Export] public ItemList GroupsList;
	[Export] public ItemList BlocksList;

	private VoxelColor[] _colors;
	private VoxelAuxData _auxData;

	private Dictionary<uint, Dictionary<string, List<ushort>>> _hierarchy = new();

	private List<uint> _displayedTypes = new();
	private List<string> _displayedGroups = new();
	private List<ushort> _displayedBlocks = new();

	private uint _selectedType;

	public override void _Ready()
	{
		LoadData();
		BuildHierarchy();

		TypesList.ItemSelected += OnTypeSelected;
		GroupsList.ItemSelected += OnGroupSelected;
		BlocksList.ItemSelected += OnBlockSelected;

		PopulateTypes();
		
		Visible = false;
		if (CameraController != null)
		{
			UpdateCameraBlockSelection(CameraController.SelectedVoxelIndex);
		}
	}

	public override void _Input(InputEvent @event)
	{
		if (@event is InputEventKey keyEvent && keyEvent.Pressed && !keyEvent.Echo && keyEvent.Keycode == Key.Tab)
		{
			ToggleUI();
		}
	}

	public void ToggleUI()
	{
		Visible = !Visible;

		if (Visible)
		{
			Input.MouseMode = Input.MouseModeEnum.Visible;
			if (CameraController != null) CameraController.IsUiOpen = true;
		}
		else
		{
			Input.MouseMode = Input.MouseModeEnum.Captured;
			if (CameraController != null) CameraController.IsUiOpen = false;
		}
	}

	private void LoadData()
	{
		_colors = VoxelData.LoadColors();

		if (!FileAccess.FileExists(AuxJsonPath))
		{
			GD.PrintErr($"Nie znaleziono pliku: {AuxJsonPath}");
			_auxData = new VoxelAuxData();
			return;
		}

		using var file = FileAccess.Open(AuxJsonPath, FileAccess.ModeFlags.Read);
		string jsonText = file.GetAsText();
		_auxData = JsonSerializer.Deserialize<VoxelAuxData>(jsonText) ?? new VoxelAuxData();
	}

	private static uint GetVoxelType(ushort index)
	{
		return (uint)((index >> 11) & 0x1F);
	}

	private void BuildHierarchy()
	{
		_hierarchy.Clear();
		HashSet<ushort> groupedVoxels = new();

		foreach (var kvp in _auxData.Groups)
		{
			string groupName = kvp.Key;
			List<ushort> indices = kvp.Value;

			if (indices == null || indices.Count == 0) continue;

			uint type = GetVoxelType(indices[0]);

			if (!_hierarchy.ContainsKey(type))
				_hierarchy[type] = new Dictionary<string, List<ushort>>();

			_hierarchy[type][groupName] = new List<ushort>(indices);

			foreach (var idx in indices)
				groupedVoxels.Add(idx);
		}

		foreach (var kvp in _auxData.VoxelNames)
		{
			if (ushort.TryParse(kvp.Key, out ushort index))
			{
				if (!groupedVoxels.Contains(index))
				{
					uint type = GetVoxelType(index);
					if (!_hierarchy.ContainsKey(type))
						_hierarchy[type] = new Dictionary<string, List<ushort>>();

					string defaultGroup = "Other";
					if (!_hierarchy[type].ContainsKey(defaultGroup))
						_hierarchy[type][defaultGroup] = new List<ushort>();

					_hierarchy[type][defaultGroup].Add(index);
				}
			}
		}
	}

	private void PopulateTypes()
	{
		TypesList.Clear();
		_displayedTypes.Clear();

		for (uint t = 0; t < 32; t++)
		{
			string typeName = _auxData.TypeNames.TryGetValue(t.ToString(), out string name) ? name : "";


			bool hasContent = _hierarchy.ContainsKey(t) && _hierarchy[t].Count > 0;
			if (string.IsNullOrWhiteSpace(typeName) && !hasContent)
				continue;

			string displayTitle = string.IsNullOrWhiteSpace(typeName) ? $"Typ {t}" : $"[{t}] {typeName}";
			TypesList.AddItem(displayTitle);
			_displayedTypes.Add(t);
		}

		if (_displayedTypes.Count > 0)
		{
			TypesList.Select(0);
			OnTypeSelected(0);
		}
	}

	private void OnTypeSelected(long itemIndex)
	{
		_selectedType = _displayedTypes[(int)itemIndex];
		GroupsList.Clear();
		BlocksList.Clear();
		_displayedGroups.Clear();
		_displayedBlocks.Clear();

		if (!_hierarchy.TryGetValue(_selectedType, out var groups))
			return;

		foreach (var groupName in groups.Keys)
		{
			GroupsList.AddItem(groupName);
			_displayedGroups.Add(groupName);
		}

		if (_displayedGroups.Count > 0)
		{
			GroupsList.Select(0);
			OnGroupSelected(0);
		}
	}

	private void OnGroupSelected(long itemIndex)
	{
		string selectedGroup = _displayedGroups[(int)itemIndex];
		BlocksList.Clear();
		_displayedBlocks.Clear();

		if (!_hierarchy.TryGetValue(_selectedType, out var groups) || !groups.TryGetValue(selectedGroup, out var blocks))
			return;

		foreach (ushort voxelIndex in blocks)
		{
			string voxelName = _auxData.VoxelNames.TryGetValue(voxelIndex.ToString(), out string name)
				? name
				: $"Block #{voxelIndex}";

			Texture2D colorIcon = CreateColorIcon(voxelIndex);
			BlocksList.AddItem($"{voxelName} ({voxelIndex})", colorIcon);
			_displayedBlocks.Add(voxelIndex);
		}
	}

	private void OnBlockSelected(long itemIndex)
	{
		ushort selectedVoxelIndex = _displayedBlocks[(int)itemIndex];
		UpdateCameraBlockSelection(selectedVoxelIndex);
	}

	private Texture2D CreateColorIcon(ushort index)
	{
		Image img = Image.CreateEmpty(24, 24, false, Image.Format.Rgba8);
		img.Fill(GetVoxelColor(index));
		return ImageTexture.CreateFromImage(img);
	}
	private void UpdateCameraBlockSelection(ushort voxelIndex)
	{
		if (CameraController == null) return;

		string voxelName = _auxData.VoxelNames.TryGetValue(voxelIndex.ToString(), out string name)
			? name
			: $"Block #{voxelIndex}";

		Color voxelColor = GetVoxelColor(voxelIndex);

		CameraController.SetSelectedBlock(voxelIndex, voxelName, voxelColor);
		GD.Print($"Selected block: {voxelName} ({voxelIndex})");
	}

	private Color GetVoxelColor(ushort index)
	{
		if (_colors != null && index < _colors.Length)
		{
			var vc = _colors[index];
			if (vc.Index == index || index == 0)
			{
				return new Color(vc.R, vc.G, vc.B, 1.0f);
			}
		}
		return Colors.Black;
	}
	
}
