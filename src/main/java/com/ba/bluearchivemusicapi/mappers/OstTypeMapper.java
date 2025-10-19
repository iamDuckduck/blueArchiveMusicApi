package com.ba.bluearchivemusicapi.mappers;

import com.ba.bluearchivemusicapi.dtos.OstTypeDTO;
import com.ba.bluearchivemusicapi.entities.OstType;
import org.mapstruct.Mapper;

import java.util.List;

@Mapper(componentModel = "spring")
public interface OstTypeMapper {
    List<OstTypeDTO> toDTOList(Iterable<OstType> ostTypes);
}
