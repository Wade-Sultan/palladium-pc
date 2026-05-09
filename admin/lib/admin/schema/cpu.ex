defmodule Admin.Schema.CPU do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, Ecto.UUID, autogenerate: true}

  schema "cpus" do
    # Virtual fields populated via JOIN with pc_parts in item_query
    field :name, :string, virtual: true
    field :manufacturer, :string, virtual: true
    field :model_number, :string, virtual: true
    field :year_released, :integer, virtual: true
    field :is_active, :boolean, virtual: true, default: true

    # CPU-specific columns
    field :brand, :string
    field :socket, :string
    field :tdp_watts, :integer
    field :has_igpu, :boolean, default: false
    field :ddr_generation, {:array, :string}
    field :supported_features, {:array, :string}
    field :benchmark_scores, :map
    field :cores, :integer
    field :threads, :integer
    field :base_clock_ghz, :float
    field :boost_clock_ghz, :float
    field :l3_cache_mb, :integer
    field :pcie_generation, :integer
    field :max_memory_gb, :integer
    field :series, :string

    # Virtual string fields for array/map form inputs
    field :ddr_generation_input, :string, virtual: true
    field :supported_features_input, :string, virtual: true
    field :benchmark_scores_input, :string, virtual: true
  end

  def changeset(cpu, attrs, _metadata \\ %{}) do
    cpu
    |> cast(attrs, [
      :name, :manufacturer, :model_number, :year_released, :is_active,
      :brand, :socket, :tdp_watts, :has_igpu,
      :cores, :threads, :base_clock_ghz, :boost_clock_ghz,
      :l3_cache_mb, :pcie_generation, :max_memory_gb, :series,
      :ddr_generation_input, :supported_features_input, :benchmark_scores_input
    ])
    |> convert_array(:ddr_generation_input, :ddr_generation)
    |> convert_array(:supported_features_input, :supported_features)
    |> convert_json(:benchmark_scores_input, :benchmark_scores)
    |> validate_required([:name, :brand, :socket, :tdp_watts, :has_igpu, :cores, :threads, :ddr_generation])
    |> prepare_changes(&upsert_pc_part(&1, "cpu"))
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
