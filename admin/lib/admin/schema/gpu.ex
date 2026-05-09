defmodule Admin.Schema.GPU do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, Ecto.UUID, autogenerate: true}

  schema "gpus" do
    field :name, :string, virtual: true
    field :manufacturer, :string, virtual: true
    field :model_number, :string, virtual: true
    field :year_released, :integer, virtual: true
    field :is_active, :boolean, virtual: true, default: true

    field :chipset, :string
    field :brand, :string
    field :vram_gb, :integer
    field :tdp_watts, :integer
    field :length_mm, :integer
    field :pcie_power_pins, :string
    field :recommended_psu_watts, :integer
    field :supported_features, {:array, :string}
    field :benchmark_scores, :map
    field :vram_type, :string
    field :width_slots, :float
    field :pcie_generation, :integer
    field :base_clock_mhz, :integer
    field :boost_clock_mhz, :integer
    field :has_ray_tracing, :boolean
    field :cuda_cores, :integer
    field :tensor_cores, :integer
    field :stream_processors, :integer
    field :matrix_cores, :integer
    field :display_outputs, :string
    field :hdmi_version, :string
    field :dp_version, :string

    field :supported_features_input, :string, virtual: true
    field :benchmark_scores_input, :string, virtual: true
  end

  def changeset(gpu, attrs, _metadata \\ %{}) do
    gpu
    |> cast(attrs, [
      :name, :manufacturer, :model_number, :year_released, :is_active,
      :chipset, :brand, :vram_gb, :tdp_watts, :length_mm,
      :pcie_power_pins, :recommended_psu_watts,
      :vram_type, :width_slots, :pcie_generation,
      :base_clock_mhz, :boost_clock_mhz, :has_ray_tracing,
      :cuda_cores, :tensor_cores, :stream_processors, :matrix_cores,
      :display_outputs, :hdmi_version, :dp_version,
      :supported_features_input, :benchmark_scores_input
    ])
    |> convert_array(:supported_features_input, :supported_features)
    |> convert_json(:benchmark_scores_input, :benchmark_scores)
    |> validate_required([:name, :chipset, :brand, :vram_gb, :tdp_watts, :length_mm])
    |> prepare_changes(&upsert_pc_part(&1, "gpu"))
  end

  defp convert_array(changeset, from_field, to_field) do
    case get_change(changeset, from_field) do
      nil -> changeset
      "" -> put_change(changeset, to_field, [])
      str -> put_change(changeset, to_field, str |> String.split(~r/,\s*/) |> Enum.reject(&(&1 == "")))
    end
  end

  defp convert_json(changeset, from_field, to_field) do
    case get_change(changeset, from_field) do
      nil -> changeset
      "" -> put_change(changeset, to_field, nil)
      str ->
        case Jason.decode(str) do
          {:ok, map} when is_map(map) -> put_change(changeset, to_field, map)
          _ -> add_error(changeset, from_field, "must be valid JSON object")
        end
    end
  end

  defp upsert_pc_part(changeset, part_type) do
    repo = changeset.repo
    id = get_field(changeset, :id)

    %Admin.Schema.PCPart{id: id}
    |> Ecto.Changeset.cast(
      %{
        name: get_field(changeset, :name),
        manufacturer: get_field(changeset, :manufacturer),
        model_number: get_field(changeset, :model_number),
        year_released: get_field(changeset, :year_released),
        is_active: get_field(changeset, :is_active) || true,
        part_type: part_type
      },
      [:name, :manufacturer, :model_number, :year_released, :is_active, :part_type]
    )
    |> repo.insert!(
      on_conflict: {:replace_all_except, [:id, :part_type, :created_at]},
      conflict_target: :id
    )

    changeset
  end
end
