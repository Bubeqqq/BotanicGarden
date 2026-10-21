using Godot;
using System;

public partial class AudioControl : HSlider
{
	[Export] private AudioStreamPlayer _audioPlayer;
	// Called when the node enters the scene tree for the first time.
	public override void _Ready()
	{
	}

	// Called every frame. 'delta' is the elapsed time since the previous frame.
	public override void _Process(double delta)
	{
	}
	public void _on_value_volume_changed(float value){
		_audioPlayer.VolumeDb = Mathf.LinearToDb((float)value);
		
	}
}
