using Godot;
using System;
public partial class Back : Button
{
	// Called when the node enters the scene tree for the first time.
	public override void _Ready()
	{
	}

	// Called every frame. 'delta' is the elapsed time since the previous frame.
	public override void _Process(double delta)
	{
	}
	public void _on_back_pressed()
	{
		HSlider vol_slider = GetNode<HSlider>($"../AudioControl");
		AppSettings settings=new AppSettings();
		settings.Volume=vol_slider.Value;
		SettingsManager.Save(settings);
	Panel options = GetNode<Panel>($"../../OptionsPanel");
	options.Visible = false;
	VBoxContainer main_buttons = GetNode<VBoxContainer>($"../../MainButtons");
	main_buttons.Visible=true;
	}
}
