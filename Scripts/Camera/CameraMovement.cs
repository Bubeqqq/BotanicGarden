using Godot;
using System;

public partial class CameraMovement : CharacterBody3D
{
    [Export] public float Speed = 5;
    
    [Export] public float Sensitivity = 0.005f;

    private Camera3D _camera;
    
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
    }

    public override void _Ready()
    {
        Input.SetMouseMode(Input.MouseModeEnum.Captured);
        
        _camera = GetNode<Node3D>("Camera3D") as Camera3D;

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
    }
}
