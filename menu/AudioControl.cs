using BotanicGarden.Common.Settings;
using Godot;
using System;

namespace BotanicGarden.Menu;

public partial class AudioControl : HSlider
{
    [Export] private AudioStreamPlayer _audioPlayer;
    // Called when the node enters the scene tree for the first time.
    public override void _Ready()
    {
        DragEnded += OnVolumeDragEnded;
        ValueChanged += OnVolumeValueChanged;
    }

    // Called every frame. 'delta' is the elapsed time since the previous frame.
    public override void _Process(double delta)
    {
        
    }
    public void OnVolumeValueChanged(double value)
    {
        SettingsManager.Volume = value;
    }

    public void OnVolumeDragEnded(bool valueChanged)
    {
        if(valueChanged) SettingsManager.Save();
    }
}
