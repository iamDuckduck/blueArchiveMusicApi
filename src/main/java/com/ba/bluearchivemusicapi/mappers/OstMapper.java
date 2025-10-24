package com.ba.bluearchivemusicapi.mappers;

import com.ba.bluearchivemusicapi.dtos.OstDTO;
import com.ba.bluearchivemusicapi.dtos.OstEditDTO;
import com.ba.bluearchivemusicapi.dtos.OstPageDTO;
import com.ba.bluearchivemusicapi.entities.OST;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import org.mapstruct.MappingTarget;

import java.util.List;

@Mapper(componentModel = "spring")
public interface OstMapper {

    @Mapping(source = "id", target = "id")
    OstDTO toDTO(OST ost);

    List<OstDTO> toDTOs(List<OST> ostList);

    @Mapping(source = "ostType.id", target = "ostTypeId")
    @Mapping(source = "ostType.name", target = "volumeName")
    @Mapping(source = "ostType.volume", target = "volume")
    OstPageDTO toOstPageDTO(OST ost);

    void updateOstFromOstEditDTO(OstEditDTO ostEditDTO, @MappingTarget OST ost);
}
