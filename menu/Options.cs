using Godot;
using System;

public partial class Options : Button
{
	// Called when the node enters the scene tree for the first time.
	public override void _Ready()
	{
	}

	// Called every frame. 'delta' is the elapsed time since the previous frame.
	public override void _Process(double delta)
	{
	}
	public void _on_options_pressed()
	{
	Panel options = GetNode<Panel>($"../../OptionsPanel");
	options.Visible = true;
	VBoxContainer main_buttons = GetNode<VBoxContainer>($"..");
		main_buttons.Visible=false;
	}
}
