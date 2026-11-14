using Godot;
using System;

public partial class MainMenu : Control
{
	[Export] private AudioStreamPlayer _audioPlayer;
	// Called when the node enters the scene tree for the first time.
	public override void _Ready()
	{
		Panel options = GetNode<Panel>("OptionsPanel");
		options.Visible = false;
		VBoxContainer main_buttons = GetNode<VBoxContainer>("MainButtons");
		main_buttons.Visible=true;
		HSlider vol_slider = GetNode<HSlider>($"OptionsPanel/AudioControl");
		_audioPlayer.Playing=true;
		
		AppSettings settings=SettingsManager.Load();
		vol_slider.Value=settings.Volume;
		_audioPlayer.VolumeDb = Mathf.LinearToDb((float)settings.Volume);
	}

	// Called every frame. 'delta' is the elapsed time since the previous frame.
	public override void _Process(double delta)
	{
		
	}
	
}
