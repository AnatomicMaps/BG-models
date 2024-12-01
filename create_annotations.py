from rdflib import Graph, Literal, RDF, URIRef, Namespace
from rdflib.namespace import DCTERMS
import pathlib
from lxml import etree


_LOCAL_ID_COUNTER = 1024

OMEXlib = Namespace('http://omex-library.org/')
LOCAL = Namespace('http://omex-library.org/annotations.ttl#')
BQBIOL = Namespace('http://biomodels.net/biology-qualifiers/')
UBERON = Namespace('http://purl.obolibrary.org/obo/UBERON_')
OPB = Namespace('http://bhi.washington.edu/OPB#')

# OPB:00154 = fluid volume
VOLUME_URI = OPB['OPB_00154']
# OPB:00509 = fluid pressure
PRESSURE_URI = OPB['OPB_00509']
# FMA:9670 = portion of blood
# UBERON:0000178 = Blood: A fluid that is composed of blood plasma and erythrocytes
BLOOD_URI = UBERON['0000178']


def _get_local_id():
    global _LOCAL_ID_COUNTER
    _LOCAL_ID_COUNTER += 1
    return URIRef(f'local-node-{_LOCAL_ID_COUNTER}')


def get_model_ids(model_string):
    root = etree.fromstring(model_string)
    namespace = "http://www.cellml.org/metadata/1.0#"
    attribute_name = "id"

    # Collect attributes with the given name and namespace
    attributes = []
    for elem in root.iter():
        # Fully qualified attribute name with namespace
        qualified_name = f"{{{namespace}}}{attribute_name}"
        if qualified_name in elem.attrib:
            attributes.append(elem.attrib[qualified_name])

    volume_ids = []
    pressure_ids = []
    flow_ids = []
    for value in attributes:
        if value.endswith('.blood.volume'):
            volume_ids.append(value)
        elif value.endswith('.blood.pressure'):
            pressure_ids.append(value)
        elif value.endswith('.blood.flow'):
            flow_ids.append(value)
        else:
            print(f'Unknown ID: {value}')

    return {
        'volume_ids': volume_ids,
        'pressure_ids': pressure_ids,
        'flow_ids': flow_ids
    }


def map_to_uberon_cavity(cavity_abbr):
    cavity_map = {
        'lv': '0016514', # Luminal space of the left ventricle of the heart
        'rv': '0016509', # Luminal space of the right ventricle of the heart.
        'la': '0016513', # Luminal space of the left atrium of the heart
        'ra': '0016522', # luminal space of the right atrium of the heart
        'pa': '0002012', # the actual artery - might not be the right term?
        'lung': '0000102', # lung vasculature: The lung vasculature is composed of the tubule structures that carry blood or lymph in the lungs
        'pulm-vein': '0002016', # pulmonary vein: Pulmonary veins are blood vessels that transport blood from the lungs to the heart
        'brain': '0008998', # vasculature of brain: System pertaining to blood vessels in the brain
        'brain-vein': '2005031', # dorsal longitudinal vein: Vessel that connects to the primitive hindbrain channel and the basilar artery at the caudal end of the medulla oblongata. Isogai et al. 2001
        'aa': '0001496', # ascending aorta:
        'celiac': '0001640', # celiac artery: The first major branch of the abdominal aorta.
        'sup-mes': '0001182', # superior mesenteric artery
        'stomach': '0000945', # stomach (there is an FMA term for vasulature of the stomach / gastric vasulature)
        'spleen': '0036301', # vasculature of spleen
        'pancreas': '0001264', # pancreas
        'intestine': '0000160', # intestine
        'colon': '0001155', # colon
        'portal-vein': '0002017', # portal vein
        'liver': '0006877' # vasculature of liver
    }
    if cavity_abbr in cavity_map.keys():
        return UBERON[cavity_map[cavity_abbr]]
    else:
        print(f'Unknown cavity abbreviation: {cavity_abbr}')
    return UBERON['0001062'] # anatomical entity


def create_local_blood_cavity_definition(rdf_graph, cavity_uri):
    # check if a suitable local entity exists
    query = """
        SELECT ?subject
        WHERE {
            ?subject ?predicate ?object
        }
    """
    results = rdf_graph.query(query, initBindings={
        'predicate': BQBIOL['isPartOf'],
        'object': cavity_uri
    })
    for row in results:
        #print(f'Found an existing local node to use: {row.subject}')
        return row.subject

    local_node = LOCAL[_get_local_id()]
    rdf_graph.add((local_node, BQBIOL['is'], BLOOD_URI))
    rdf_graph.add((local_node, BQBIOL['isPartOf'], cavity_uri))
    return local_node


def create_blood_volume_annotation(rdf_graph, model, model_id):
    model_uri = OMEXlib[f'{model.as_posix()}#{model_id}']
    cavity = model_id.split('.')[0]
    cavity_uri = map_to_uberon_cavity(cavity)
    local_node = create_local_blood_cavity_definition(rdf_graph, cavity_uri)
    rdf_graph.add((model_uri, BQBIOL['isPropertyOf'], local_node))
    rdf_graph.add((model_uri, BQBIOL['isVersionOf'], VOLUME_URI))


def create_blood_pressure_annotation(rdf_graph, model, model_id):
    model_uri = OMEXlib[f'{model.as_posix()}#{model_id}']
    cavity = model_id.split('.')[0]
    cavity_uri = map_to_uberon_cavity(cavity)
    local_node = create_local_blood_cavity_definition(rdf_graph, cavity_uri)
    rdf_graph.add((model_uri, BQBIOL['isPropertyOf'], local_node))
    rdf_graph.add((model_uri, BQBIOL['isVersionOf'], PRESSURE_URI))


if __name__ == "__main__":
    cellml_dir = pathlib.Path('models')
    cellml_file = cellml_dir / 'cvs-model.cellml'
    if cellml_file.is_file():
        model_string = cellml_file.read_text()
        #print(model_string)
        model_ids = get_model_ids(model_string)
        #print(model_ids)
    else:
        print(f"CellML model file doesn't exist: {cellml_file}")
        exit(-1)

    g = Graph()
    g.bind('OPB', OPB)
    g.bind('UBERON', UBERON)
    g.bind('OMEXlib', OMEXlib)
    g.bind('local', LOCAL)
    g.bind('bqbiol', BQBIOL)

    for volume in model_ids['volume_ids']:
        create_blood_volume_annotation(g, cellml_file, volume)
    for pressure in model_ids['pressure_ids']:
        create_blood_pressure_annotation(g, cellml_file, pressure)

    with open('annotations.ttl', 'w') as f:
        f.write(g.serialize(format='ttl'))
