defmodule Admin.Schema.PSU do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, Ecto.UUID, autogenerate: true}

  schema "psus" do
    field :name, :string, virtual: true
    field :manufacturer, :string, virtual: true
    field :model_number, :string, virtual: true
    field :year_released, :integer, virtual: true
    field :is_active, :boolean, virtual: true, default: true

    field :wattage, :integer
    field :form_factor, :string
    field :efficiency_rating, :string
    field :pcie_8pin_connectors, :integer
    field :pcie_12pin_connectors, :integer
    field :pcie_16pin_connectors, :integer
    field :depth_mm, :integer
    field :modular, :string
    field :eps_connectors, :integer
    field :fan_size_mm, :integer
    field :is_fanless, :boolean
  end

  def changeset(psu, attrs, _metadata \\ %{}) do
    psu
    |> cast(attrs, [
      :name, :manufacturer, :model_number, :year_released, :is_active,
      :wattage, :form_factor, :efficiency_rating,
      :pcie_8pin_connectors, :pcie_12pin_connectors, :pcie_16pin_connectors,
      :depth_mm, :modular, :eps_connectors, :fan_size_mm, :is_fanless
    ])
    |> validate_required([:name, :wattage, :form_factor, :efficiency_rating])
    |> prepare_changes(&upsert_pc_part(&1, "psu"))
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
