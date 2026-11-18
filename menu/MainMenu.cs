using Godot;
using System;
using BotanicGarden.Common.Settings;

namespace BotanicGarden.Menu;

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
        vol_slider.Value = Settings.Volume;
        _audioPlayer.VolumeDb = Mathf.LinearToDb((float)Settings.Volume);
    }

    // Called every frame. 'delta' is the elapsed time since the previous frame.
    public override void _Process(double delta)
    {
        
    }
    
}
