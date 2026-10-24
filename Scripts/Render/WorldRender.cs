using Godot;
using System;
using System.Collections.Generic;

public struct ComputeShader
{
    public Rid Shader, Pipeline;

    public Rid[] UniformSets;
    
    public byte[] PushConstant;
    
    public bool AddBarier;
    
    public Rid UniformSetAtoB, UniformSetBtoA;

    public double Timer { get; set; }
    public double TimePerSimulation;
}

public partial class WorldRender : Node3D
{
    private RenderingDevice _rd;
    private Rid _texA, _texB;

    private List<ComputeShader> _computeShaders = new();
    
    private Texture3Drd _displayTexA;
    private Texture3Drd _displayTexB;
    private ShaderMaterial _material;

    private List<MeshInstance3D> _chunks = new();
    private int _chunkWidth = 16, _chunkDepth = 16, _chunkHeight = 16;
    private int _chunkVoxelCount => _chunkWidth * _chunkDepth * _chunkHeight;
    
    private bool _useAtoB = true;
    private int _gridWidth = 256, _gridDepth = 256, _gridHeight = 100;
    private Vector3 _workGroupSize = new Vector3(8, 4, 8);
    private float _voxelSize = 0.1f;
    private float _spacing = 1.0f;
    private float _chunkSpacing = 1.0f;
    
    private int _voxelCount => _gridWidth * _gridDepth * _gridHeight;
    
    private double _timer = 0.0;

    private float _renderDistance = 80.0f;
    
    public override void _Ready()
    {
        GD.Print("Voxel Renderer");
        
        var player = GetNode<CharacterBody3D>("Player");
        if (player is CameraMovement mv)
        {
            mv.ExpandChunks += () => {if (_chunkSpacing < 5) _chunkSpacing += 0.1f;UpdateSpacing();};
            mv.ShrinkChunks += () => {
                if (_chunkSpacing > 1.1f)
                {
                    _chunkSpacing -= 0.1f;
                    UpdateSpacing();
                }else if (_chunkSpacing != 1.0f)
                {
                    _chunkSpacing = 1f;
                    UpdateSpacing();
                }

            };
            mv.ExpandVoxels += () => {if (_spacing < 5) _spacing += 0.1f;UpdateSpacing();};
            mv.ShrinkVoxels += () =>
            {
                if (_spacing > 1.1f)
                {
                    _spacing -= 0.1f;
                    UpdateSpacing();
                }else if (_spacing != 1.0f)
                {
                    _spacing = 1f;
                    UpdateSpacing();
                }
            };
        }

        SetBackground(new Color(0.1f, 0.15f, 0.25f));
        AddLight();
        
        _rd = RenderingServer.GetRenderingDevice();
        
        SetupMaterial();
        SetupChunks();
        SetupPingPongBuffers();
        
        AddComputeShader("res://Scripts/ComputeShaders/compute_example.glsl", true, 0.02f);


        GD.Print("Done");
    }

    private void UpdateSpacing()
    {
        _material.SetShaderParameter("spacing", _spacing);
        _material.SetShaderParameter("chunk_spacing", _chunkSpacing);
        
        SetupChunks();
    }

    private void AddLight()
    {
        var light = new DirectionalLight3D();
        AddChild(light);
        light.RotationDegrees = new Vector3(-45, 45, 0);
    }

    private void SetBackground(Color color)
    {
        var env = new Godot.Environment();
        env.BackgroundMode = Godot.Environment.BGMode.Color;
        env.BackgroundColor = color;

        var environment = new WorldEnvironment();
        environment.Environment = env;
        AddChild(environment);
    }

    private void SetupMaterial()
    {
        /*_material = new ShaderMaterial();
        _material.Shader = GD.Load<Shader>("res://Scripts/Render/voxel_material.gdshader");
        _material.SetShaderParameter("grid_width", _gridWidth);
        _material.SetShaderParameter("grid_depth", _gridDepth);
        _material.SetShaderParameter("grid_height", _gridHeight);
        _material.SetShaderParameter("spacing", _spacing);
        _material.SetShaderParameter("voxel_size", _voxelSize);
        _material.SetShaderParameter("chunk_spacing", _chunkSpacing);
        _material.SetShaderParameter("chunk_size", new Vector3I(_chunkWidth, _chunkHeight, _chunkDepth));*/
        
        _material = new ShaderMaterial();
        _material.Shader = GD.Load<Shader>("res://Scripts/Render/dda_render.gdshader");
        _material.SetShaderParameter("grid_size", new Vector3I(_chunkWidth, _chunkHeight, _chunkDepth));
        _material.SetShaderParameter("box_size", new Vector3(_chunkWidth, _chunkHeight, _chunkDepth) * _voxelSize * _spacing);
    }

    private void SetupChunks()
    {
        var chunkCountX = Math.Ceiling((float)_gridWidth / _chunkWidth);
        var chunkCountY = Math.Ceiling((float)_gridHeight / _chunkHeight);
        var chunkCountZ = Math.Ceiling((float)_gridDepth / _chunkDepth);

        foreach (var chunk in _chunks) RemoveChild(chunk);
        _chunks.Clear();
        
        var dimensions = new Vector3(_chunkWidth, _chunkHeight, _chunkDepth) * _voxelSize * _spacing;
        
        var boxMesh = new BoxMesh();
        boxMesh.Size = dimensions;
        boxMesh.SurfaceSetMaterial(0, _material);
        
        for (var x = 0; x < chunkCountX; x++)
        {
            for (var y = 0; y < chunkCountY; y++)
            {
                for (var z = 0; z < chunkCountZ; z++)
                {
                    var chunkObj = new MeshInstance3D();
                    chunkObj.Mesh = boxMesh;

                    chunkObj.Position = new Vector3(
                        x * _chunkWidth, 
                        y * _chunkHeight, 
                        z * _chunkDepth
                    ) * _voxelSize * _spacing + (dimensions / 2.0f);
                
                    chunkObj.VisibilityRangeEnd = _renderDistance;
                    chunkObj.VisibilityRangeFadeMode = GeometryInstance3D.VisibilityRangeFadeModeEnum.Disabled;
                
                    AddChild(chunkObj);
                    _chunks.Add(chunkObj);
                }
            }
        }
    }
    
    private void AddComputeShader(string computePath, bool addBarrierAfter, float timePerSimulation, Rid[] uniformSets = null, byte[] pushConstant = null)
    {
        var shaderFile = GD.Load<RDShaderFile>(computePath);
        if (shaderFile == null)
        {
            GD.PrintErr($"Nie znaleziono pliku Compute Shadera pod ścieżką: {computePath}");
            SetProcess(false);
            return;
        }

        var shader = _rd.ShaderCreateFromSpirV(shaderFile.GetSpirV());
        if (!shader.IsValid)
        {
            GD.PrintErr("Plik .glsl nie skompilował się");
            SetProcess(false);
            return;
        }

        var pipeline = _rd.ComputePipelineCreate(shader);
        
        var uniformInA = new RDUniform { UniformType = RenderingDevice.UniformType.Image, Binding = 0 };
        uniformInA.AddId(_texA);
        var uniformOutB = new RDUniform { UniformType = RenderingDevice.UniformType.Image, Binding = 1 };
        uniformOutB.AddId(_texB);
        var uniformIn = _rd.UniformSetCreate(new Godot.Collections.Array<RDUniform> { uniformInA, uniformOutB }, shader, 0);

        var uniformInB = new RDUniform { UniformType = RenderingDevice.UniformType.Image, Binding = 0 };
        uniformInB.AddId(_texB);
        var uniformOutA = new RDUniform { UniformType = RenderingDevice.UniformType.Image, Binding = 1 };
        uniformOutA.AddId(_texA);
        var uniformOut = _rd.UniformSetCreate(new Godot.Collections.Array<RDUniform> { uniformInB, uniformOutA }, shader, 0);
        
        var computeShader = new ComputeShader
        {
            Pipeline = pipeline, 
            Shader = shader, 
            AddBarier = addBarrierAfter,
            PushConstant = pushConstant,
            UniformSets = uniformSets,
            UniformSetAtoB = uniformIn,
            UniformSetBtoA = uniformOut,
            TimePerSimulation = timePerSimulation
        };
        
        _computeShaders.Add(computeShader);
    }

    private void SetupPingPongBuffers()
    {
        var fmt = new RDTextureFormat {
            Width = (uint)_gridWidth,
            Height = (uint)_gridHeight,
            Depth = (uint)_gridDepth,
            Format = RenderingDevice.DataFormat.R16G16B16A16Uint,
            UsageBits = RenderingDevice.TextureUsageBits.StorageBit | 
                        RenderingDevice.TextureUsageBits.SamplingBit | 
                        RenderingDevice.TextureUsageBits.CanUpdateBit | 
                        RenderingDevice.TextureUsageBits.CanCopyFromBit,
            TextureType = RenderingDevice.TextureType.Type3D
        };
        var view = new RDTextureView();

        // float[] initialData = new float[_voxelCount];
        // for (int i = 0; i < _voxelCount; i++) initialData[i] = GD.Randf();

        var randomNumber = new RandomNumberGenerator();
        var initialData = new short[_voxelCount * 4];
        for (var i = 0; i < _voxelCount; i++)
        {
            //rainbow
            //initialData[idx] = (short)(i % 254 + 1);
            var x = i % _gridWidth;
            var y = (i / _gridWidth) % _gridHeight;
            var z = i / (_gridWidth * _gridHeight);
            
            var idx = i * 4;

            if(y <= 3)
                initialData[idx] = 6;
            else if (y == 4 && x % 16 == 0 && z % 16 == 0)
                initialData[idx] = 2;
            else
                initialData[idx] = 1;
                    
            initialData[idx + 1] = 1;
            initialData[idx + 2] = 1;
            initialData[idx + 3] = 1;
        }

        //initialData[200000] = 2;
        
        byte[] initialBytes = new byte[_voxelCount * 8];
        Buffer.BlockCopy(initialData, 0, initialBytes, 0, initialBytes.Length);

        _texA = _rd.TextureCreate(fmt, view, new Godot.Collections.Array<byte[]> { initialBytes });
        _texB = _rd.TextureCreate(fmt, view, new Godot.Collections.Array<byte[]> { new byte[_voxelCount * 8] });

        _displayTexA = new Texture3Drd() { TextureRdRid = _texA };
        _displayTexB = new Texture3Drd { TextureRdRid = _texB };
        _material.SetShaderParameter("image", _displayTexA);
    }

    public override void _Process(double delta)
    {
        var computeList = _rd.ComputeListBegin();
        bool gridChanged = false;
        
        for(var j = 0; j < _computeShaders.Count; j++)
        {
            var shader = _computeShaders[j];
            shader.Timer += delta;

            if (shader.Timer > shader.TimePerSimulation)
            {
                shader.Timer -= shader.TimePerSimulation;
                shader.PushConstant = BitConverter.GetBytes(GD.Randi());
                _computeShaders[j] = shader;
            }
            else
            {
                _computeShaders[j] = shader;
                continue;
            }

            gridChanged = true;
            _rd.ComputeListBindComputePipeline(computeList, shader.Pipeline);
            
            var currentUniformSet = _useAtoB ? shader.UniformSetAtoB : shader.UniformSetBtoA;
            _rd.ComputeListBindUniformSet(computeList, currentUniformSet, 0);

            if (shader.UniformSets != null)
            {
                for (uint i = 0; i < shader.UniformSets.Length; i++)
                {
                    _rd.ComputeListBindUniformSet(computeList, shader.UniformSets[i], i + 1);
                }
            }

            if (shader.PushConstant is {Length: > 0})
            {
                _rd.ComputeListSetPushConstant(computeList, shader.PushConstant, (uint)shader.PushConstant.Length);
            }
            
            _rd.ComputeListDispatch(computeList, 
                (uint)Mathf.CeilToInt(_gridWidth / _workGroupSize.X), 
                (uint)Mathf.CeilToInt(_gridHeight / _workGroupSize.Y), 
                (uint)Mathf.CeilToInt(_gridDepth / _workGroupSize.Z));
            
            if (shader.AddBarier)
            {
                _rd.ComputeListAddBarrier(computeList);
            }
        }
        
        _rd.ComputeListEnd();

        if (gridChanged)
        {
            _material.SetShaderParameter("image", _useAtoB ? _displayTexB : _displayTexA);
            _useAtoB = !_useAtoB;
        }
    }
    
    public override void _Notification(int what)
    {
        if (what == NotificationPredelete && _rd != null)
        {
            if (_texA.IsValid)
            {
                _displayTexA.TextureRdRid = new Rid();
                _rd.FreeRid(_texA);
            }
            if (_texB.IsValid)
            {
                _displayTexB.TextureRdRid = new Rid();
                _rd.FreeRid(_texB);
            }

            foreach (var shader in _computeShaders)
            {
                if(shader.Shader.IsValid) _rd.FreeRid(shader.Shader);
            }
        }
    }
}

