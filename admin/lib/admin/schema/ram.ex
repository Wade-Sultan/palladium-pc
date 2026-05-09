defmodule Admin.Schema.RAM do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, Ecto.UUID, autogenerate: true}

  schema "ram" do
    field :name, :string, virtual: true
    field :manufacturer, :string, virtual: true
    field :model_number, :string, virtual: true
    field :year_released, :integer, virtual: true
    field :is_active, :boolean, virtual: true, default: true

    field :ddr_generation, :string
    field :speed_mhz, :integer
    field :modules, :integer
    field :capacity_gb, :integer
    field :height_mm, :integer
    field :module_capacity_gb, :integer
    field :cas_latency, :integer
    field :voltage, :float
    field :has_rgb, :boolean
    field :is_ecc, :boolean
  end

  def changeset(ram, attrs, _metadata \\ %{}) do
    ram
    |> cast(attrs, [
      :name, :manufacturer, :model_number, :year_released, :is_active,
      :ddr_generation, :speed_mhz, :modules, :capacity_gb, :height_mm,
      :module_capacity_gb, :cas_latency, :voltage, :has_rgb, :is_ecc
    ])
    |> validate_required([:name, :ddr_generation, :speed_mhz, :modules, :capacity_gb])
    |> prepare_changes(&upsert_pc_part(&1, "ram"))
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
