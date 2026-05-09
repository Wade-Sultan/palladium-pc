defmodule Admin.Schema.Motherboard do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, Ecto.UUID, autogenerate: true}

  schema "motherboards" do
    field :name, :string, virtual: true
    field :manufacturer, :string, virtual: true
    field :model_number, :string, virtual: true
    field :year_released, :integer, virtual: true
    field :is_active, :boolean, virtual: true, default: true

    field :socket, :string
    field :form_factor, :string
    field :ddr_generation, :string
    field :memory_slots, :integer
    field :has_wifi, :boolean, default: false
    field :m2_slots, :integer
    field :m2_pcie_gen, :integer
    field :chipset, :string
    field :max_memory_gb, :integer
    field :sata_ports, :integer
    field :pcie_x16_slots, :integer
    field :pcie_generation, :integer
    field :has_bluetooth, :boolean
    field :usb_type_a_count, :integer
    field :usb_type_c_count, :integer
    field :audio_codec, :string
  end

  def changeset(mobo, attrs, _metadata \\ %{}) do
    mobo
    |> cast(attrs, [
      :name, :manufacturer, :model_number, :year_released, :is_active,
      :socket, :form_factor, :ddr_generation, :memory_slots, :has_wifi,
      :m2_slots, :m2_pcie_gen, :chipset, :max_memory_gb, :sata_ports,
      :pcie_x16_slots, :pcie_generation, :has_bluetooth,
      :usb_type_a_count, :usb_type_c_count, :audio_codec
    ])
    |> validate_required([:name, :socket, :form_factor, :ddr_generation, :memory_slots, :has_wifi])
    |> prepare_changes(&upsert_pc_part(&1, "motherboard"))
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
