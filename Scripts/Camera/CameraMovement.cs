using Godot;
using System;

public partial class CameraMovement : CharacterBody3D
{
	[Export] public float Speed = 5;
	[Export] public WorldRender worldRender;
	
	[Export] public float Sensitivity = 0.005f;
	[Export] public int InteractionRadius = 10;
	[Export] public float InteractionDensity = 0.5f;

	[Export] public float RadiusChangeSpeed = 10.0f; 
	[Export] public float DensityChangeSpeed = 0.2f;

	[Export] public Label RadiusLabel;
	[Export] public Label DensityLabel;

	private Camera3D _camera;
	private float _exactRadius;
	
	[Signal]
	public delegate void ExpandChunksEventHandler();
	
	[Signal]
	public delegate void ShrinkChunksEventHandler();
	
	[Signal]
	public delegate void ExpandVoxelsEventHandler();
	
	[Signal]
	public delegate void ShrinkVoxelsEventHandler();
	
	public override void _PhysicsProcess(double delta)
	{
		base._PhysicsProcess(delta);

		var velocity = Vector3.Zero;
		
		if (Input.IsActionPressed("move_right"))
		{
			velocity.X += 1.0f;
		}

		if (Input.IsActionPressed("move_left"))
		{
			velocity.X -= 1.0f;
		}
		
		if (Input.IsActionPressed("move_up"))
		{
			velocity.Y += 1.0f;
		}
		
		if (Input.IsActionPressed("move_down"))
		{
			velocity.Y -= 1.0f;
		}
		
		if (Input.IsActionPressed("move_forward"))
		{
			velocity.Z -= 1.0f;
		}
		
		if (Input.IsActionPressed("move_back"))
		{
			velocity.Z += 1.0f;
		}
		
		var targetVelocity = Vector3.Zero;
		
		targetVelocity = velocity * Speed * (Input.IsActionPressed("ctrl") ? 2 : 1);
		
		targetVelocity = targetVelocity.Rotated(Vector3.Up, _camera.Rotation.Y);
		
		
		Velocity = targetVelocity;
		MoveAndSlide();
	}

	public override void _Process(double delta)
	{
		bool uiNeedsUpdate = false;
		float fDelta = (float)delta;

		if (Input.IsActionJustPressed("i"))
		{
			EmitSignal(SignalName.ExpandChunks);
		}
		if (Input.IsActionJustPressed("k"))
		{
			EmitSignal(SignalName.ShrinkChunks);
		}
		if (Input.IsActionJustPressed("o"))
		{
			EmitSignal(SignalName.ExpandVoxels);
		}
		if (Input.IsActionJustPressed("l"))
		{
			EmitSignal(SignalName.ShrinkVoxels);
		}
		if (Input.IsActionPressed("radius_up"))
		{
			_exactRadius += RadiusChangeSpeed * fDelta;
			uiNeedsUpdate = true;
		}
		if (Input.IsActionPressed("radius_down"))
		{
			_exactRadius -= RadiusChangeSpeed * fDelta;
			_exactRadius = Mathf.Max(0.0f, _exactRadius); 
			uiNeedsUpdate = true;
		}
		
		if (uiNeedsUpdate)
		{
			InteractionRadius = Mathf.RoundToInt(_exactRadius); 
		}

		
		if (Input.IsActionPressed("density_up"))
		{
			InteractionDensity += DensityChangeSpeed * fDelta;
			InteractionDensity = Mathf.Min(1.0f, InteractionDensity);
			uiNeedsUpdate = true;
		}
		if (Input.IsActionPressed("density_down"))
		{
			InteractionDensity -= DensityChangeSpeed * fDelta;
			InteractionDensity = Mathf.Max(0.0f, InteractionDensity);
			uiNeedsUpdate = true;
		}

		if (uiNeedsUpdate)
		{
			UpdateUI();
		}
		if (worldRender != null)
		{
			Vector3 rayDir = -_camera.GlobalTransform.Basis.Z.Normalized();
			worldRender.UpdateHighlightRay(_camera.GlobalPosition, rayDir, 20.0f, InteractionRadius);
		}
	}

	public override void _Ready()
	{
		Input.SetMouseMode(Input.MouseModeEnum.Captured);
		
		_camera = GetNode<Node3D>("Camera3D") as Camera3D;
		_exactRadius = InteractionRadius;
		UpdateUI();

	}
	private void UpdateUI()
	{
		if (RadiusLabel != null)
			RadiusLabel.Text = $"Radius: {InteractionRadius}";
			
		if (DensityLabel != null)
			DensityLabel.Text = $"Density: {InteractionDensity:F2}";
	}

	public override void _UnhandledInput(InputEvent @event)
{
	if (@event is InputEventMouseMotion mouseMotion)
	{
		var rotation = _camera.Rotation;
		rotation.X -= mouseMotion.Relative.Y * Sensitivity;
		rotation.Y -= mouseMotion.Relative.X * Sensitivity;
		rotation.X = Mathf.Clamp(rotation.X, Mathf.DegToRad(-89f), Mathf.DegToRad(89f));
		_camera.Rotation = rotation;
	}
	

	if (@event is InputEventMouseButton mouseButton && mouseButton.Pressed)
	{
		
		if (worldRender == null) return; 
		GD.Print("Clicked mouse button, raycast requested.");
		Vector3 rayDir = -_camera.GlobalTransform.Basis.Z.Normalized();
		Vector3 startPos = _camera.GlobalPosition;
		float interactionRange = 20.0f; 

		if (mouseButton.ButtonIndex == MouseButton.Left)
		{
			GD.Print("Clicked left");
			
			worldRender.RequestGpuRaycast(startPos, rayDir, interactionRange, 0); 
			
		}
		else if (mouseButton.ButtonIndex == MouseButton.Right)
		{
			worldRender.RequestGpuRaycast(startPos, rayDir, interactionRange, 4100, InteractionRadius, InteractionDensity); 
			GD.Print("Clicked right - AoE Place");
		}
	}
	
}
}
