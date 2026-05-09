defmodule Admin.Schema.CPUCooler do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, Ecto.UUID, autogenerate: true}

  schema "cpu_coolers" do
    field :name, :string, virtual: true
    field :manufacturer, :string, virtual: true
    field :model_number, :string, virtual: true
    field :year_released, :integer, virtual: true
    field :is_active, :boolean, virtual: true, default: true

    field :supported_sockets, {:array, :string}
    field :cooler_type, :string
    field :max_tdp_watts, :integer
    field :height_mm, :integer
    field :radiator_size_mm, :integer
    field :fan_count, :integer
    field :fan_size_mm, :integer
    field :noise_dba, :float
    field :has_rgb, :boolean

    field :supported_sockets_input, :string, virtual: true
  end

  def changeset(cooler, attrs, _metadata \\ %{}) do
    cooler
    |> cast(attrs, [
      :name, :manufacturer, :model_number, :year_released, :is_active,
      :cooler_type, :max_tdp_watts, :height_mm, :radiator_size_mm,
      :fan_count, :fan_size_mm, :noise_dba, :has_rgb,
      :supported_sockets_input
    ])
    |> convert_array(:supported_sockets_input, :supported_sockets)
    |> validate_required([:name, :cooler_type, :supported_sockets])
    |> prepare_changes(&upsert_pc_part(&1, "cpucooler"))
  end

  defp convert_array(changeset, from_field, to_field) do
    case get_change(changeset, from_field) do
      nil -> changeset
      "" -> put_change(changeset, to_field, [])
      str -> put_change(changeset, to_field, str |> String.split(~r/,\s*/) |> Enum.reject(&(&1 == "")))
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
