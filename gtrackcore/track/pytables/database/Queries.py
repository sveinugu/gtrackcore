from gtrackcore.track.pytables.database.Database import DatabaseReader
from gtrackcore.util.CustomExceptions import ShouldNotOccurError
from gtrackcore.util.pytables.NameFunctions import get_database_filename, get_br_table_node_names, \
    get_track_table_node_names


class DatabaseQueries(object):

    def __init__(self, genome, track_name, allow_overlaps):
        self._genome = genome
        self._track_name = track_name
        self._allow_overlaps = allow_overlaps

        database_filename = get_database_filename(genome, track_name, allow_overlaps=allow_overlaps)
        self._db_reader = DatabaseReader(database_filename)


class BoundingRegionQueries(DatabaseQueries):

    def __init__(self, genome, track_name, allow_overlaps):
        super(BoundingRegionQueries, self).__init__(genome, track_name, allow_overlaps)
        self._table_node_names = get_br_table_node_names(genome, track_name, allow_overlaps)


    def total_element_count_for_chr(self, chromosome):
        self._db_reader.open()
        table = self._db_reader.get_table(self._table_node_names)

        result = [row['element_count'] for row in table.where('(chr == region_chr)',
                                                              condvars={'region_chr': chromosome})]

        self._db_reader.close()

        return sum(result) if len(result) > 0 else 0

    def enclosing_bounding_region_for_region(self, genome_region):
        query = '(chr == region_chr) & (start <= region_start) & (end >= region_end)'
        return self._all_bounding_regions_for_region(genome_region, query)

    def all_bounding_regions_enclosed_by_region(self, genome_region):
        query = '(chr == region_chr) & (start >= region_start) & (end < region_end)'
        return self._all_bounding_regions_for_region(genome_region, query)

    def all_bounding_regions_touched_by_region(self, genome_region):
        query = '(chr == region_chr) & (start < region_end) & (end > region_start)'
        return self._all_bounding_regions_for_region(genome_region, query)

    def all_bounding_regions(self):
        self._db_reader.open()
        table = self._db_reader.get_table(self._table_node_names)

        bounding_regions = [{'chr': row['chr'],
                             'start': row['start'],
                             'end': row['end'],
                             'start_index': row['start_index'],
                             'end_index': row['end_index']}
                            for row in table]

        self._db_reader.close()

        return bounding_regions

    def _all_bounding_regions_for_region(self, genome_region, query):
        self._db_reader.open()
        table = self._db_reader.get_table(self._table_node_names)

        bounding_regions = [{'chr': row['chr'],
                             'start': row['start'],
                             'end': row['end'],
                             'start_index': row['start_index'],
                             'end_index': row['end_index']}
                            for row in table.where(query,
                                                   condvars={
                                                       'region_chr': genome_region.chr,
                                                       'region_start': genome_region.start,
                                                       'region_end': genome_region.end
                                                   })]

        self._db_reader.close()

        return bounding_regions


class TrackQueries(DatabaseQueries):

    def __init__(self, genome, track_name, allow_overlaps):
        super(TrackQueries, self).__init__(genome, track_name, allow_overlaps)
        self._table_node_names = get_track_table_node_names(genome, track_name, allow_overlaps)

    @staticmethod
    def _build_start_and_end_index_queries(track_format):
        if track_format.isSegment():
            start_index_query = '(start >= region_start) | ((end > region_start) & (start < region_end))'
            end_index_query = '(start > region_end)'

        elif track_format.isPoint():
            start_index_query = '(start >= region_start) & (start < region_end)'
            end_index_query = '(start > region_end)'

        elif track_format.isPartition():
            start_index_query = '(end >= region_start) & (end <= region_end)'
            end_index_query = '(end >= region_end)'

        else:
            raise ShouldNotOccurError

        return start_index_query, end_index_query

    def start_and_end_indices(self, genome_region, track_format):
        assert genome_region.genome == self._genome

        br_queries = BoundingRegionQueries(self._genome, self._track_name, self._allow_overlaps)
        bounding_region = br_queries.enclosing_bounding_region_for_region(genome_region)

        if len(bounding_region) > 0:
            br_start_index, br_end_index = (bounding_region[0]['start_index'], bounding_region[0]['end_index'])
        else:
            return 0, 0  # if region is empty

        if track_format.reprIsDense():
            start_index = br_start_index + (genome_region.start - bounding_region[0]['start'])
            end_index = start_index + len(genome_region)
        else:
            start_index, end_index = self._get_region_start_and_end_indices(genome_region, br_start_index,
                                                                            br_end_index, track_format)
            #start_index, end_index = self._get_region_start_and_end_index_for_segments_and_points_tracks(
            #    genome_region, br_start_index, br_end_index)

        return start_index, end_index

    def _get_first_index(self, table, query, condvars, start, stop):
        for row in table.where(query, start=start, stop=stop, condvars=condvars):
            return row.nrow
        return None

    def _get_region_start_and_end_indices(self, genome_region, br_start, br_stop, track_format):
        start_index_query, end_index_query = self._build_start_and_end_index_queries(track_format)

        self._db_reader.open()
        table = self._db_reader.get_table(self._table_node_names)

        condvars = {
            'region_start': genome_region.start,
            'region_end': genome_region.end
        }

        start_index = self._get_first_index(table, start_index_query, condvars, br_start, br_stop)
        end_index = self._get_first_index(table, end_index_query, condvars, br_start, br_stop)

        self._db_reader.close()

        if track_format.isPartition() and end_index is not None:
            end_index += 1

        if start_index is not None and end_index is None:
            end_index = br_stop

        if start_index is None and end_index is None:
            return 0, 0
        else:
            return start_index, end_index

    def _get_region_start_and_end_index_for_segments_tracks(self, genome_region, br_start, br_stop):
        self._db_reader.open()
        table = self._db_reader.get_table(self._table_node_names)
        start_index = self._get_region_start_index_for_segments(table, genome_region, br_start, br_stop)
        end_index = self._get_region_end_index_for_segments_and_points_tracks(table, genome_region, br_start, br_stop)
        self._db_reader.close()

        return (start_index, end_index) if end_index > start_index else (0, 0)

    def _get_region_start_index_for_segments(self, table, genome_region, lower_limit, upper_limit):
        while upper_limit - lower_limit > 1000:
            mid_index = lower_limit + ((upper_limit - lower_limit) / 2)
            row = table[mid_index]

            if row['start'] > genome_region.start:
                upper_limit = mid_index
            else:
                lower_limit = mid_index

        for row in table.iterrows(start=lower_limit, stop=upper_limit):
            if row['start'] < genome_region.start > row['end'] or row['start'] > genome_region.start:
                return row.nrow

    def _get_region_end_index_for_segments_and_points_tracks(self, table, genome_region, lower_limit, upper_limit):
        while upper_limit - lower_limit > 1000:
            mid_index = lower_limit + ((upper_limit - lower_limit) / 2)
            row = table[mid_index]

            if row['start'] > genome_region.end:
                upper_limit = mid_index
            else:
                lower_limit = mid_index

        for row in table.iterrows(start=lower_limit, stop=upper_limit):
            if row['start'] > genome_region.end:
                return row.nrow

        return upper_limit
