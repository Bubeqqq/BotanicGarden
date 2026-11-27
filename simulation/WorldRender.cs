using Godot;
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using BotanicGarden.WorldGen;
using System.Reflection.Metadata;
// using System.Numerics;

namespace BotanicGarden.Simulation;

[StructLayout(LayoutKind.Sequential)]
public struct InteractionPushConstant
{
	public float StartX, StartY, StartZ, MaxDist;
	public float DirX, DirY, DirZ;
	public int ActionType;
	public int Radius;
	public float Seed;
	public float Density;
	private float _pad0;
}
public partial class WorldRender : Node3D
{
	//Options
	
	//  -World size
	private const int _chunkWidth = 32, _chunkDepth = 32, _chunkHeight = 32;
	private const int _gridWidth = 256, _gridDepth = 256, _gridHeight = 128;
	private const int _minTerrainHeight = 10, _maxTerrainHeight = 60;
	private const float _waterPercentage = 0.4f;
	
	//  -GPU
	private Vector3 _workGroupSize = new Vector3(8, 4, 8);
	
	//  -Render
	private float _voxelSize = 0.1f;
	private float _renderDistance = 40.0f;
	
	//Calculations
	
	private int VoxelCount => _gridWidth * _gridDepth * _gridHeight;
	private int ChunkVoxelCount => _chunkWidth * _chunkDepth * _chunkHeight;
	
	// Render
	
	private readonly List<MeshInstance3D> _chunks = [];
	
	private bool _useAtoB = true;
	private RenderingDevice _rd;
	private Rid _texA, _texB;
	
	private Texture3Drd _displayTexA;
	private Texture3Drd _displayTexB;
	private ShaderMaterial _material;
	
	// Compute Shader
	
	private Rid _shader, _pipeline;
	private Rid _uniformSetAtoB, _uniformSetBtoA;
	private double _timer = 0.0;
	private double _timePerSimulation;
	

	private Rid _interactionShader, _interactionPipeline;
	private Rid _interactUniformSetA, _interactUniformSetB;
	private bool _interactionRequested = false;
	private InteractionPushConstant _interactionData;
	//--------------
	
	// Compute Shader data Buffers
	private Rid _voxelData;
	private Rid _plantIndex;
	
	//References

	//Block Highlight
	private Rid _highlightTex;
	private Texture2Drd _displayHighlightTex;
	private bool _highlightRequested = false;
	private InteractionPushConstant _highlightData;
    
    //Analysis Shader
    private Rid _analysisShader, _analysisPipeline;
    private Rid _analysisUniformSetA;
    private Rid _analysisVoxelCount;
    private int _framesPerAnalysis = 20;
    private int _frameTimer = 0;
    private uint _analysisBufferSize;
    
    private readonly byte[] _simPushConstant = new byte[4];
    private readonly byte[] _interactPushBytes = new byte[Marshal.SizeOf<InteractionPushConstant>()];
    private Callable _onAnalysisCompletedCallable;
    
	//Analysis
	public event Action<GardenAnalysisSnapshot> AnalysisUpdated;
	public GardenAnalysisSnapshot LatestAnalysis { get; private set; }
	private double _totalSimTime = 0.0;
    //FPS counter
    
    private double _fpsAccumTime = 0.0;
    private int _fpsFrames = 0;
    private int _currentFps = 0;

    private int _simStepsCounter = 0;
    private double _currentSimStepsPerSec = 0.0;
	
	public override void _Ready()
	{
		GD.Print("Voxel Renderer");

		SetBackground(new Color(0.1f, 0.15f, 0.25f));
		AddLight();
		
		_rd = RenderingServer.GetRenderingDevice();
		
		SetupMaterial();
		ApplyColorsAs2DTexture();
		SetupChunks();
		SetupPingPongBuffers();
        
        _onAnalysisCompletedCallable = Callable.From<byte[]>(OnAnalysisCompleted);
		
		SetupComputeShaderData("res://voxel_data/voxel_data.json");
		SetComputeShader("res://simulation/compute/main.glsl", 0.02f);

		SetupInteractionShader("res://simulation/compute/interaction.glsl");
        SetupAnalysisShader("res://simulation/compute/Analysis.glsl");
        
		GD.Print("Done");
	}

    public void SetTransparentSoil(bool transparent)
    {
        _material.SetShaderParameter("transparent_soils", transparent);
    }
    
    public void SetTerrainVisualisation(bool visualisation)
    {
        _material.SetShaderParameter("show_territories", visualisation);
    }
    
	private void SetupInteractionShader(string path)
	{
		var shaderFile = GD.Load<RDShaderFile>(path);
		_interactionShader = _rd.ShaderCreateFromSpirV(shaderFile.GetSpirV());
		_interactionPipeline = _rd.ComputePipelineCreate(_interactionShader);

		var fmt = new RDTextureFormat {
			Width = 1, Height = 1, Depth = 1,
			Format = RenderingDevice.DataFormat.R16G16B16A16Uint,
			UsageBits = RenderingDevice.TextureUsageBits.StorageBit | RenderingDevice.TextureUsageBits.SamplingBit,
			TextureType = RenderingDevice.TextureType.Type2D
		};
		_highlightTex = _rd.TextureCreate(fmt, new RDTextureView(), new Godot.Collections.Array<byte[]> { new byte[8] });
		
		_displayHighlightTex = new Texture2Drd { TextureRdRid = _highlightTex };
		_material.SetShaderParameter("highlight_data", _displayHighlightTex); 


		var uniformA = new RDUniform { UniformType = RenderingDevice.UniformType.Image, Binding = 0 };
		uniformA.AddId(_texA);
		var uniformA_HL = new RDUniform { UniformType = RenderingDevice.UniformType.Image, Binding = 1 };
		uniformA_HL.AddId(_highlightTex);
		_interactUniformSetA = _rd.UniformSetCreate(new Godot.Collections.Array<RDUniform> { uniformA, uniformA_HL }, _interactionShader, 0);

		var uniformB = new RDUniform { UniformType = RenderingDevice.UniformType.Image, Binding = 0 };
		uniformB.AddId(_texB);
		var uniformB_HL = new RDUniform { UniformType = RenderingDevice.UniformType.Image, Binding = 1 };
		uniformB_HL.AddId(_highlightTex);
		_interactUniformSetB = _rd.UniformSetCreate(new Godot.Collections.Array<RDUniform> { uniformB, uniformB_HL }, _interactionShader, 0);
	}

    public void SetupAnalysisShader(string path)
    {
        var shaderFile = GD.Load<RDShaderFile>(path);
        _analysisShader = _rd.ShaderCreateFromSpirV(shaderFile.GetSpirV());
        _analysisPipeline = _rd.ComputePipelineCreate(_analysisShader);
        
        _analysisBufferSize = (ushort.MaxValue + 1) * sizeof(uint);
        _analysisVoxelCount = _rd.StorageBufferCreate(_analysisBufferSize);

        var uniformA = new RDUniform { UniformType = RenderingDevice.UniformType.Image, Binding = 0 };
        uniformA.AddId(_texA);

        var voxelCountUniform = new RDUniform { UniformType = RenderingDevice.UniformType.StorageBuffer, Binding = 1 };
        voxelCountUniform.AddId(_analysisVoxelCount);

        var voxelDataUniform = new RDUniform { UniformType = RenderingDevice.UniformType.StorageBuffer, Binding = 2 };
        voxelDataUniform.AddId(_voxelData);

        _analysisUniformSetA = _rd.UniformSetCreate(
            new Godot.Collections.Array<RDUniform> { uniformA, voxelCountUniform, voxelDataUniform },
            _analysisShader, 0);
    }
    
    
	public void RequestGpuRaycast(Vector3 start, Vector3 dir, float maxDist, int actionType, int radius = 0, float density = 1.0f)
	{
		start /= _voxelSize;
		maxDist /= _voxelSize;

		_interactionData = new InteractionPushConstant
		{
			StartX = start.X, StartY = start.Y, StartZ = start.Z, MaxDist = maxDist,
			DirX = dir.X, DirY = dir.Y, DirZ = dir.Z, ActionType = actionType,
			Radius = radius,
			Seed = (float)GD.RandRange(0.0, 100.0),
			Density = density
		};
		_interactionRequested = true;
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
		_material.Shader = GD.Load<Shader>("res://legacy/render/voxel_material.gdshader");
		_material.SetShaderParameter("grid_width", _gridWidth);
		_material.SetShaderParameter("grid_depth", _gridDepth);
		_material.SetShaderParameter("grid_height", _gridHeight);
		_material.SetShaderParameter("spacing", _spacing);
		_material.SetShaderParameter("voxel_size", _voxelSize);
		_material.SetShaderParameter("chunk_spacing", _chunkSpacing);
		_material.SetShaderParameter("chunk_size", new Vector3I(_chunkWidth, _chunkHeight, _chunkDepth));*/
		
		_material = new ShaderMaterial();
		_material.Shader = GD.Load<Shader>("res://simulation/render/dda_render.gdshader");
		_material.SetShaderParameter("grid_size", new Vector3I(_chunkWidth, _chunkHeight, _chunkDepth));
		_material.SetShaderParameter("box_size", new Vector3(_chunkWidth, _chunkHeight, _chunkDepth) * _voxelSize);
	}

	private void SetupChunks()
	{
		var chunkCountX = Math.Ceiling((float)_gridWidth / _chunkWidth);
		var chunkCountY = Math.Ceiling((float)_gridHeight / _chunkHeight);
		var chunkCountZ = Math.Ceiling((float)_gridDepth / _chunkDepth);

		foreach (var chunk in _chunks) RemoveChild(chunk);
		_chunks.Clear();
		
		var dimensions = new Vector3(_chunkWidth, _chunkHeight, _chunkDepth) * _voxelSize;
		
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
					) * _voxelSize + (dimensions / 2.0f);
				
					chunkObj.VisibilityRangeEnd = _renderDistance;
					chunkObj.VisibilityRangeFadeMode = GeometryInstance3D.VisibilityRangeFadeModeEnum.Disabled;
				
					AddChild(chunkObj);
					_chunks.Add(chunkObj);
				}
			}
		}
	}

	private void SetupComputeShaderData(string path)
	{
		var voxelData = VoxelData.LoadStruct(path);
		byte[] voxelByte = MemoryMarshal.AsBytes(voxelData.AsSpan()).ToArray();
		_voxelData = _rd.StorageBufferCreate((uint)voxelByte.Length, voxelByte);
		
		byte[] plantIndexByte = BitConverter.GetBytes((uint)0);
		_plantIndex = _rd.StorageBufferCreate((uint) plantIndexByte.Length, plantIndexByte);
	}
	
	private void SetComputeShader(string computePath, float timePerSimulation)
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
		
		var voxelDataUniform = new RDUniform { UniformType = RenderingDevice.UniformType.StorageBuffer, Binding = 2 };
		voxelDataUniform.AddId(_voxelData);
		
		var plantIndexUniform = new RDUniform { UniformType = RenderingDevice.UniformType.StorageBuffer, Binding = 3 };
		plantIndexUniform.AddId(_plantIndex);
		
		var uniformInA = new RDUniform { UniformType = RenderingDevice.UniformType.Image, Binding = 0 };
		uniformInA.AddId(_texA);
		var uniformOutB = new RDUniform { UniformType = RenderingDevice.UniformType.Image, Binding = 1 };
		uniformOutB.AddId(_texB);
		var uniformIn = _rd.UniformSetCreate(new Godot.Collections.Array<RDUniform> { uniformInA, uniformOutB, voxelDataUniform, plantIndexUniform}, shader, 0);

		var uniformInB = new RDUniform { UniformType = RenderingDevice.UniformType.Image, Binding = 0 };
		uniformInB.AddId(_texB);
		var uniformOutA = new RDUniform { UniformType = RenderingDevice.UniformType.Image, Binding = 1 };
		uniformOutA.AddId(_texA);
		var uniformOut = _rd.UniformSetCreate(new Godot.Collections.Array<RDUniform> { uniformInB, uniformOutA, voxelDataUniform, plantIndexUniform}, shader, 0);
		
		_pipeline = pipeline; 
		_shader = shader;
		_uniformSetAtoB = uniformIn;
		_uniformSetBtoA = uniformOut;
		_timePerSimulation = timePerSimulation;
	}
	
	private void ApplyColorsAs2DTexture()
	{
		const int textureSize = 256;
		var image = Image.CreateEmpty(textureSize, textureSize, false, Image.Format.Rgba8);
		var colors = VoxelData.LoadColors();
		
		for (var i = 0; i < colors.Length; i++)
		{
			var x = i % textureSize;
			var y = i / textureSize;
			
			var color = new Color(colors[i].R,  colors[i].G, colors[i].B, colors[i].A);
			image.SetPixel(x, y, color);
		}

		var texture = ImageTexture.CreateFromImage(image);
		_material.SetShaderParameter("color_palette", texture);
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

		// Generate World
		var worldSize = new Vector3I(_gridWidth, _gridHeight, _gridDepth);
		var initialData = WorldGenerator.Generate(worldSize, _minTerrainHeight, _maxTerrainHeight, _waterPercentage);
		
		byte[] initialBytes = new byte[VoxelCount * 8];
		Buffer.BlockCopy(initialData, 0, initialBytes, 0, initialBytes.Length);

		_texA = _rd.TextureCreate(fmt, view, new Godot.Collections.Array<byte[]> { initialBytes });
		_texB = _rd.TextureCreate(fmt, view, new Godot.Collections.Array<byte[]> { new byte[VoxelCount * 8] });

		_displayTexA = new Texture3Drd() { TextureRdRid = _texA };
		_displayTexB = new Texture3Drd { TextureRdRid = _texB };
		_material.SetShaderParameter("image", _displayTexA);
	}
	private static int GetStageIndex(uint voxelCount) => voxelCount switch
	{
		<= 4 => 0,   // Very Small
		<= 15 => 1,  // Small
		<= 45 => 2,  // Medium
		_ => 3       // Big
	};  
	private void OnAnalysisCompleted(byte[] rawBytes)
	{
		ReadOnlySpan<uint> voxelCounts = MemoryMarshal.Cast<byte, uint>(rawBytes);
		var aggregated = new Dictionary<uint, (int plants, long voxels, int[] stages)>();

		int totalPlants = 0;
		long totalVoxels = 0;
		uint maxVoxels = 0;
		uint maxSpecies = 0;

		for (int i = 0; i < voxelCounts.Length; i++)
		{
			uint packed = voxelCounts[i];
			uint count = packed & 0x1FFFFFu;
			if (count == 0) continue;

			uint species = packed >> 21;
			totalPlants++;
			totalVoxels += count;

			if (count > maxVoxels)
			{
				maxVoxels = count;
				maxSpecies = species;
			}

			int stage = GetStageIndex(count);

			if (aggregated.TryGetValue(species, out var current))
			{
				current.stages[stage]++;
				aggregated[species] = (current.plants + 1, current.voxels + count, current.stages);
			}
			else
			{
				var stages = new int[4];
				stages[stage] = 1;
				aggregated[species] = (1, count, stages);
			}
		}

		var bySpecies = new Dictionary<uint, SpeciesStats>(aggregated.Count);
		foreach (var (speciesId, data) in aggregated)
		{
			bySpecies[speciesId] = new SpeciesStats(speciesId, data.plants, data.voxels, data.stages);
		}

		LatestAnalysis = new GardenAnalysisSnapshot
		{
			SimTimeSeconds = _totalSimTime,
			TotalPlants = totalPlants,
			TotalPlantVoxels = totalVoxels,
			Fps = _currentFps,
			SimStepsPerSec = _currentSimStepsPerSec,
			LargestPlantSpeciesId = maxSpecies,
			LargestPlantVoxels = maxVoxels,
			BySpecies = bySpecies
		};

		AnalysisUpdated?.Invoke(LatestAnalysis);
	}
    
	public override void _Process(double delta)
    {
        _fpsAccumTime += delta;
        _fpsFrames++;

        if (_fpsAccumTime >= 0.5)
        {
            _currentFps = Mathf.RoundToInt(_fpsFrames / _fpsAccumTime);
            _currentSimStepsPerSec = _simStepsCounter / _fpsAccumTime;

            GD.Print($"FPS: {_currentFps} | Sim/s: {_currentSimStepsPerSec:0.0}");

            _fpsAccumTime = 0.0;
            _fpsFrames = 0;
            _simStepsCounter = 0;
        }
        
        _timer += delta;

        if (_timer > _timePerSimulation)
        {
            _timer -= _timePerSimulation;
            _frameTimer += 1;
            _simStepsCounter++;
			_totalSimTime += _timePerSimulation;
        }
        else
        {
            return;
        }

        uint groupsX = (uint)Mathf.CeilToInt(_gridWidth / _workGroupSize.X);
        uint groupsY = (uint)Mathf.CeilToInt(_gridHeight / _workGroupSize.Y);
        uint groupsZ = (uint)Mathf.CeilToInt(_gridDepth / _workGroupSize.Z);

        bool runAnalysis = _frameTimer >= _framesPerAnalysis && _useAtoB;
        if (runAnalysis)
        {
            _frameTimer = 0;
            _rd.BufferClear(_analysisVoxelCount, 0, _analysisBufferSize);
        }
        
        if (_interactionRequested || _highlightRequested)
        {
            var interactList = _rd.ComputeListBegin();
            _rd.ComputeListBindComputePipeline(interactList, _interactionPipeline);

            var interactSet = _useAtoB ? _interactUniformSetA : _interactUniformSetB;
            _rd.ComputeListBindUniformSet(interactList, interactSet, 0);

            var currentData = _interactionRequested ? _interactionData : _highlightData;
            MemoryMarshal.Write(_interactPushBytes, in currentData);

            _rd.ComputeListSetPushConstant(interactList, _interactPushBytes, (uint)_interactPushBytes.Length);
            _rd.ComputeListDispatch(interactList, 1, 1, 1);
            _rd.ComputeListEnd();

            _interactionRequested = false;
            _highlightRequested = false;
        }
        
        if (runAnalysis)
        {
            var analysisList = _rd.ComputeListBegin();
            _rd.ComputeListBindComputePipeline(analysisList, _analysisPipeline);
            _rd.ComputeListBindUniformSet(analysisList, _analysisUniformSetA, 0);
            _rd.ComputeListDispatch(analysisList, groupsX, groupsY, groupsZ);
            _rd.ComputeListEnd();
        }
        
        var simList = _rd.ComputeListBegin();
        _rd.ComputeListBindComputePipeline(simList, _pipeline);

        var currentUniformSet = _useAtoB ? _uniformSetAtoB : _uniformSetBtoA;
        _rd.ComputeListBindUniformSet(simList, currentUniformSet, 0);

        BitConverter.TryWriteBytes(_simPushConstant, GD.Randi());
        _rd.ComputeListSetPushConstant(simList, _simPushConstant, (uint)_simPushConstant.Length);

        _rd.ComputeListDispatch(simList, groupsX, groupsY, groupsZ);
        _rd.ComputeListEnd();
        
        if (runAnalysis)
        {
            _rd.BufferGetDataAsync(_analysisVoxelCount, _onAnalysisCompletedCallable);
        }

        _material.SetShaderParameter("image", _useAtoB ? _displayTexB : _displayTexA);
        _useAtoB = !_useAtoB;
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
            if (_highlightTex.IsValid)
            {
                _displayHighlightTex.TextureRdRid = new Rid();
                _rd.FreeRid(_highlightTex);
            }
            
            if (_voxelData.IsValid) _rd.FreeRid(_voxelData);
            if (_plantIndex.IsValid) _rd.FreeRid(_plantIndex);
            if (_analysisVoxelCount.IsValid) _rd.FreeRid(_analysisVoxelCount);
            
            if (_shader.IsValid) _rd.FreeRid(_shader);
            if (_interactionShader.IsValid) _rd.FreeRid(_interactionShader);
            if (_analysisShader.IsValid) _rd.FreeRid(_analysisShader);
        }
    }

	public void UpdateHighlightRay(Vector3 start, Vector3 dir, float maxDist, int radius = 0)
	{
		start /= _voxelSize;
		maxDist /= _voxelSize;
		_highlightData = new InteractionPushConstant
		{
			StartX = start.X, StartY = start.Y, StartZ = start.Z, MaxDist = maxDist,
			DirX = dir.X, DirY = dir.Y, DirZ = dir.Z, ActionType = -1,
			Radius = radius,
			Seed = 0f,
			Density = 0f
		};
		_highlightRequested = true;
	}
}
