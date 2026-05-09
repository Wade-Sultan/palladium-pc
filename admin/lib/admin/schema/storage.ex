defmodule Admin.Schema.Storage do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, Ecto.UUID, autogenerate: true}

  schema "storage" do
    field :name, :string, virtual: true
    field :manufacturer, :string, virtual: true
    field :model_number, :string, virtual: true
    field :year_released, :integer, virtual: true
    field :is_active, :boolean, virtual: true, default: true

    field :storage_type, :string
    field :form_factor, :string
    field :interface, :string
    field :capacity_gb, :integer
    field :read_speed_mbps, :integer
    field :write_speed_mbps, :integer
    field :has_dram_cache, :boolean
    field :endurance_tbw, :integer
    field :rpm, :integer
  end

  def changeset(storage, attrs, _metadata \\ %{}) do
    storage
    |> cast(attrs, [
      :name, :manufacturer, :model_number, :year_released, :is_active,
      :storage_type, :form_factor, :interface, :capacity_gb,
      :read_speed_mbps, :write_speed_mbps, :has_dram_cache, :endurance_tbw, :rpm
    ])
    |> validate_required([:name, :storage_type, :form_factor, :interface, :capacity_gb])
    |> prepare_changes(&upsert_pc_part(&1, "storage"))
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
