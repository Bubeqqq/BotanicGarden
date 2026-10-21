using System.IO;
using System.Text.Json;
public static class SettingsManager
{
	private const string FilePath = "usersettings.json";

	public static void Save(AppSettings settings)
	{
		var options = new JsonSerializerOptions { WriteIndented = true };
		string json = JsonSerializer.Serialize(settings, options);
		File.WriteAllText(FilePath, json);
	}

	public static AppSettings Load()
	{
		if (!File.Exists(FilePath))
		{
			return new AppSettings();
		}

		string json = File.ReadAllText(FilePath);
		return JsonSerializer.Deserialize<AppSettings>(json) ?? new AppSettings();
	}
}
